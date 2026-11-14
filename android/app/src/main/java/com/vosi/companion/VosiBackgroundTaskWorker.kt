package com.vosi.companion

import android.app.AlarmManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.os.Build
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.Worker
import androidx.work.WorkerParameters
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.Calendar
import java.util.concurrent.TimeUnit

/**
 * Best-effort persistent task polling for low-risk Android-local actions.
 * WorkManager persists the schedule across process death and device reboot.
 * Android still controls execution timing; force-stop and battery policies can pause it.
 */
class VosiBackgroundTaskWorker(
    appContext: Context,
    workerParams: WorkerParameters
) : Worker(appContext, workerParams) {

    override fun doWork(): Result {
        val credential = DeviceCredentialStore.load(applicationContext) ?: return Result.success()
        return try {
            val baseUrl = credential.getString("backend_url").trimEnd('/')
            val deviceId = credential.getString("device_id")
            val token = credential.getString("device_token")
            val (heartbeatCode, heartbeatBody) = request(
                baseUrl, "/agent/devices/${segment(deviceId)}/heartbeat", "POST", token
            )
            if (heartbeatCode == 401 || heartbeatCode == 403) {
                postStatus("VOSI needs you to reconnect this phone", "Open VOSI and pair this phone again.")
                return Result.failure()
            }
            if (heartbeatCode !in 200..299 || !JSONObject(heartbeatBody).optBoolean("success")) {
                throw IOException("VOSI backend heartbeat failed (HTTP $heartbeatCode).")
            }
            executeAvailableTasks(baseUrl, token)
            publishTaskUpdates(baseUrl, token)
            Result.success()
        } catch (_: IOException) {
            Result.retry()
        } catch (_: Exception) {
            Result.retry()
        }
    }

    private fun executeAvailableTasks(baseUrl: String, token: String) {
        val (code, body) = request(baseUrl, "/agent/tasks/available", "GET", token)
        if (code !in 200..299) throw IOException("Task queue unavailable (HTTP $code).")
        val tasks = JSONObject(body).optJSONArray("tasks") ?: JSONArray()
        for (index in 0 until minOf(tasks.length(), 3)) {
            val task = tasks.optJSONObject(index) ?: continue
            if (task.optString("capability") !in setOf("device.alarm.create", "device.volume.set")) continue
            val taskId = task.optString("task_id")
            val (claimCode, claimBody) = request(baseUrl, "/agent/tasks/${segment(taskId)}/claim", "POST", token)
            if (claimCode !in 200..299) continue
            val step = JSONObject(claimBody).optJSONObject("step") ?: continue
            val stepId = step.optString("step_id")
            val result = try {
                val args = step.optJSONObject("arguments") ?: JSONObject()
                val confirmation = when (step.optString("capability")) {
                    "device.volume.set" -> setPhoneVolume(args)
                    "device.alarm.create" -> schedulePhoneAlarm(taskId, args)
                    else -> throw IllegalArgumentException("This Android capability is not supported in background.")
                }
                JSONObject().put("success", true).put("verified", true)
                    .put("receipt", JSONObject().put("capability", step.optString("capability"))
                        .put("confirmation", confirmation))
            } catch (error: Exception) {
                JSONObject().put("success", false).put("verified", false).put("receipt", JSONObject())
                    .put("error", (error.message ?: "Android background task failed").take(1500))
            }
            val (resultCode, _) = request(
                baseUrl, "/agent/tasks/${segment(taskId)}/steps/${segment(stepId)}/result",
                "POST", token, result
            )
            if (resultCode !in 200..299) throw IOException("Could not save the task receipt (HTTP $resultCode).")
        }
    }

    private fun setPhoneVolume(args: JSONObject): String {
        val percent = args.optInt("volume", -1)
        require(percent in 0..100) { "Phone volume must be between 0 and 100." }
        val audio = applicationContext.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val maxVolume = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        val target = (maxVolume * percent / 100.0).toInt()
        audio.setStreamVolume(AudioManager.STREAM_MUSIC, target, 0)
        check(audio.getStreamVolume(AudioManager.STREAM_MUSIC) == target) {
            "Android did not apply the requested volume."
        }
        return "Phone media volume set to $percent%."
    }

    private fun schedulePhoneAlarm(taskId: String, args: JSONObject): String {
        val hour = args.optInt("hour", -1)
        val minute = args.optInt("minute", 0)
        require(hour in 0..23 && minute in 0..59) { "Use a valid 24-hour alarm time." }
        val alarmTime = Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, hour)
            set(Calendar.MINUTE, minute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
            if (timeInMillis <= System.currentTimeMillis()) add(Calendar.DAY_OF_YEAR, 1)
        }
        val intent = Intent(applicationContext, VosiAlarmReceiver::class.java).putExtra("title", "VOSI alarm")
        val pending = PendingIntent.getBroadcast(
            applicationContext, taskId.hashCode(), intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val manager = applicationContext.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        manager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, alarmTime.timeInMillis, pending)
        return "Phone alarm scheduled for ${String.format("%02d:%02d", hour, minute)}."
    }

    private fun publishTaskUpdates(baseUrl: String, token: String) {
        val (code, body) = request(baseUrl, "/agent/tasks/updates", "GET", token)
        if (code !in 200..299) return
        val updates = JSONObject(body).optJSONArray("updates") ?: JSONArray()
        val preferences = applicationContext.getSharedPreferences("vosi_task_notifications", Context.MODE_PRIVATE)
        for (index in 0 until updates.length()) {
            val task = updates.optJSONObject(index) ?: continue
            val state = task.optString("state")
            if (state !in setOf("completed", "failed", "cancelled")) continue
            val taskId = task.optString("task_id")
            if (preferences.getString(taskId, null) == state) continue
            val steps = task.optJSONArray("steps") ?: JSONArray()
            var detail = if (state == "completed") "Task completed successfully." else "Task $state."
            for (stepIndex in 0 until steps.length()) {
                val step = steps.optJSONObject(stepIndex) ?: continue
                val receipt = step.optJSONObject("receipt")
                if (receipt != null && receipt.optString("confirmation").isNotBlank()) detail = receipt.optString("confirmation")
                if (step.optString("error").isNotBlank()) detail = step.optString("error")
            }
            postStatus(task.optString("goal", "VOSI task"), detail, state == "completed")
            preferences.edit().putString(taskId, state).apply()
        }
    }

    private fun postStatus(title: String, detail: String, completed: Boolean = false) {
        val channelId = "vosi_background_tasks"
        val manager = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(NotificationChannel(
                channelId, "VOSI background tasks", NotificationManager.IMPORTANCE_DEFAULT
            ))
        }
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(applicationContext, channelId)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(applicationContext)
        }
        val notification = builder.setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(if (completed) "VOSI task completed" else title)
            .setContentText(detail)
            .setStyle(Notification.BigTextStyle().bigText("$title\n$detail"))
            .setAutoCancel(true).build()
        try { manager.notify(title.hashCode(), notification) } catch (_: SecurityException) {
            // Execution remains valid when notification permission is denied.
        }
    }

    private fun request(
        baseUrl: String, path: String, method: String, token: String, body: JSONObject? = null
    ): Pair<Int, String> {
        val connection = URL(baseUrl + path).openConnection() as HttpURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 10000
            connection.readTimeout = 20000
            connection.setRequestProperty("Authorization", "Bearer $token")
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            return code to (stream?.bufferedReader()?.use { it.readText() } ?: "")
        } finally { connection.disconnect() }
    }

    private fun segment(value: String): String =
        java.net.URLEncoder.encode(value, Charsets.UTF_8.name()).replace("+", "%20")
}

object VosiBackgroundTaskScheduler {
    private const val PERIODIC_WORK = "vosi-background-task-poll"

    fun ensureScheduled(context: Context) {
        val constraints = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
        val periodic = PeriodicWorkRequestBuilder<VosiBackgroundTaskWorker>(15, TimeUnit.MINUTES)
            .setConstraints(constraints)
            .setBackoffCriteria(androidx.work.BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            PERIODIC_WORK, ExistingPeriodicWorkPolicy.KEEP, periodic
        )
        runSoon(context)
    }

    fun runSoon(context: Context) {
        val request = OneTimeWorkRequestBuilder<VosiBackgroundTaskWorker>()
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .setBackoffCriteria(androidx.work.BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(
            "vosi-background-task-immediate", ExistingWorkPolicy.REPLACE, request
        )
    }
}
