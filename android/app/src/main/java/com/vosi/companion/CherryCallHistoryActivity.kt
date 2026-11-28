package com.vosi.companion

import android.app.Activity
import android.app.AlertDialog
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.Spinner
import android.widget.ArrayAdapter
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.core.app.NotificationCompat
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

/** Call-history viewer for the CHERRY AI receptionist backend. */
class CherryCallHistoryActivity : Activity() {
    private lateinit var list: LinearLayout
    private lateinit var status: TextView
    private lateinit var metrics: TextView
    private lateinit var search: EditText
    private lateinit var statusFilter: Spinner
    private lateinit var urgencyFilter: Spinner
    private lateinit var callbackFilter: CheckBox
    private lateinit var previousButton: Button
    private lateinit var nextButton: Button
    private var pageOffset = 0
    private var currentTotal = 0
    private val pageSize = 25
    private val prefs by lazy { getSharedPreferences("vosi_companion_settings", Context.MODE_PRIVATE) }
    private val backendBase by lazy { prefs.getString("device_backend_url", "http://127.0.0.1:8001")!!.trimEnd('/') }

    private fun authenticatedConnection(path: String, method: String = "GET"): HttpURLConnection {
        val token = AccountSessionStore.load() ?: throw IllegalStateException("Sign in to your CHERRY AI account to view call history.")
        val conn = URL("$backendBase$path").openConnection() as HttpURLConnection
        conn.connectTimeout = 8000
        conn.readTimeout = 10000
        conn.requestMethod = method
        conn.setRequestProperty("Accept", "application/json")
        conn.setRequestProperty("Authorization", "Bearer $token")
        return conn
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(24,24,24,24) }
        root.addView(TextView(this).apply { text="CHERRY AI Call History"; textSize=24f })
        metrics = TextView(this).apply { text="Call dashboard loading…"; setPadding(0,12,0,8); textSize=14f }
        root.addView(metrics)
        status = TextView(this).apply { text="Loading calls…"; setPadding(0,8,0,8) }
        root.addView(status)
        search = EditText(this).apply { hint="Search caller, purpose or summary"; singleLine=true }
        root.addView(search)
        statusFilter = Spinner(this).apply {
            adapter = ArrayAdapter(this@CherryCallHistoryActivity, android.R.layout.simple_spinner_dropdown_item, listOf("All statuses","New","Reviewed","Callback complete"))
        }
        urgencyFilter = Spinner(this).apply {
            adapter = ArrayAdapter(this@CherryCallHistoryActivity, android.R.layout.simple_spinner_dropdown_item, listOf("All urgency","Urgent","Normal","Unknown"))
        }
        root.addView(statusFilter)
        root.addView(urgencyFilter)
        callbackFilter = CheckBox(this).apply { text="Only calls requesting a callback" }
        root.addView(callbackFilter)
        root.addView(Button(this).apply { text="Apply filters"; setOnClickListener { pageOffset=0; loadCalls() } })
        root.addView(Button(this).apply { text="Refresh"; setOnClickListener { pageOffset=0; loadCalls() } })
        val scroll=ScrollView(this)
        list=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(0,12,0,0) }
        scroll.addView(list)
        root.addView(scroll, LinearLayout.LayoutParams(-1,0,1f))
        val pagination=LinearLayout(this).apply { orientation=LinearLayout.HORIZONTAL }
        previousButton=Button(this).apply { text="Previous"; setOnClickListener { if(pageOffset>=pageSize){pageOffset-=pageSize;loadCalls()} } }
        nextButton=Button(this).apply { text="Next"; setOnClickListener { if(pageOffset+pageSize<currentTotal){pageOffset+=pageSize;loadCalls()} } }
        pagination.addView(previousButton,LinearLayout.LayoutParams(0,-2,1f))
        pagination.addView(nextButton,LinearLayout.LayoutParams(0,-2,1f))
        root.addView(pagination)
        setContentView(root)
        requestNotificationPermissionIfNeeded()
        loadCalls()
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 8802)
        }
    }

    private fun loadCalls() {
        status.text="Connecting to CHERRY AI backend…"
        val query=StringBuilder("limit=$pageSize&offset=$pageOffset")
        val selectedStatus=when(statusFilter.selectedItemPosition) {
            1 -> "new"; 2 -> "reviewed"; 3 -> "callback_done"; else -> ""
        }
        val selectedUrgency=when(urgencyFilter.selectedItemPosition) {
            1 -> "urgent"; 2 -> "normal"; 3 -> "unknown"; else -> ""
        }
        if(selectedStatus.isNotEmpty()) query.append("&status=$selectedStatus")
        if(selectedUrgency.isNotEmpty()) query.append("&urgency=$selectedUrgency")
        if(callbackFilter.isChecked) query.append("&callback_only=true")
        val q=search.text.toString().trim()
        if(q.isNotEmpty()) query.append("&q=").append(java.net.URLEncoder.encode(q,"UTF-8"))
        thread {
            try {
                val statsConn=authenticatedConnection("/call-receptionist/calls/stats")
                val statsCode=statsConn.responseCode
                val statsStream=if(statsCode in 200..299) statsConn.inputStream else statsConn.errorStream
                val statsRaw=statsStream?.bufferedReader()?.use { it.readText() } ?: "{}"
                statsConn.disconnect()
                if(statsCode !in 200..299) throw IllegalStateException("Dashboard metrics request failed (HTTP $statsCode)")
                val stats=JSONObject(statsRaw).optJSONObject("stats") ?: JSONObject()
                val conn=authenticatedConnection("/call-receptionist/calls?$query")
                val code=conn.responseCode
                val stream=if(code in 200..299) conn.inputStream else conn.errorStream
                val response=stream?.bufferedReader()?.use { it.readText() } ?: "{}"
                conn.disconnect()
                if(code !in 200..299) throw IllegalStateException("Call history request failed (HTTP $code)")
                val data=JSONObject(response)
                val calls=data.optJSONArray("calls") ?: JSONArray()
                val total=data.optInt("total",calls.length())
                runOnUiThread {
                    list.removeAllViews()
                    currentTotal=total
                    metrics.text="Total ${stats.optInt("total")}  •  New ${stats.optInt("new_count")}  •  Urgent ${stats.optInt("urgent_count")}  •  Callbacks ${stats.optInt("callback_requested_count")}"
                    status.text=if(total==0) "No calls match these filters." else "Showing ${pageOffset+1}–${minOf(pageOffset+calls.length(),total)} of $total call(s)."
                    previousButton.isEnabled=pageOffset>0
                    nextButton.isEnabled=pageOffset+pageSize<total
                    for(i in 0 until calls.length()) {
                        val item=calls.getJSONObject(i)
                        addCallCard(item)
                        notifyCallbackOrUrgent(item)
                    }
                }
            } catch(e:Exception) {
                runOnUiThread { status.text="Could not load call history or dashboard. Check backend URL and account.\n${e.message ?: "Network error"}" }
            }
        }
    }

    private fun addCallCard(c: JSONObject) {
        val id=c.optInt("id")
        val number=c.optString("caller_number","Unknown number").ifBlank { "Unknown number" }
        val summary=c.optString("summary","").ifBlank { "No summary available" }
        val urgency=c.optString("urgency","unknown")
        val callback=c.optBoolean("callback_requested")
        val card=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(16,16,16,16) }
        card.addView(TextView(this).apply { text="${if(urgency=="urgent") "⚠️ " else ""}$number"; textSize=18f })
        card.addView(TextView(this).apply { text="${c.optString("started_at")}  •  ${c.optInt("duration_seconds")} sec  •  ${c.optString("outcome")}"; textSize=12f })
        card.addView(TextView(this).apply { text=summary; textSize=14f; setPadding(0,8,0,4) })
        if(callback) card.addView(TextView(this).apply { text="📞 Callback requested"; textSize=14f })
        card.addView(TextView(this).apply { text="Status: ${c.optString("status","new")}"; textSize=12f })
        card.addView(Button(this).apply { text="Open details"; setOnClickListener { loadDetail(id) } })
        if(c.optString("status")!="callback_done") card.addView(Button(this).apply {
            text="Mark callback complete"
            setOnClickListener { updateStatus(id,"callback_done") }
        })
        if(c.optString("status")=="new") card.addView(Button(this).apply {
            text="Mark reviewed"
            setOnClickListener { updateStatus(id,"reviewed") }
        })
        card.addView(Button(this).apply {
            text="Delete call record and transcript"
            setOnClickListener {
                AlertDialog.Builder(this@CherryCallHistoryActivity)
                    .setTitle("Delete call #$id?")
                    .setMessage("This permanently deletes the saved call details and transcript.")
                    .setNegativeButton("Cancel",null)
                    .setPositiveButton("Delete") { _, _ -> deleteCall(id) }
                    .show()
            }
        })
        list.addView(card)
        list.addView(android.view.View(this).apply { setBackgroundColor(0x22000000) }, LinearLayout.LayoutParams(-1,1))
    }

    private fun loadDetail(id:Int) {
        thread {
            try {
                val conn=authenticatedConnection("/call-receptionist/calls/$id")
                val code=conn.responseCode
                val stream=if(code in 200..299) conn.inputStream else conn.errorStream
                val raw=stream?.bufferedReader()?.use { it.readText() } ?: "{}"
                conn.disconnect()
                if(code !in 200..299) throw IllegalStateException("Call detail request failed (HTTP $code)")
                val data=JSONObject(raw).getJSONObject("call")
                runOnUiThread {
                    val transcript=data.optString("transcript").ifBlank { "No transcript was captured for this call." }
                    AlertDialog.Builder(this)
                        .setTitle("Call details • #$id")
                        .setMessage("Caller: ${data.optString("caller_number")}\nOutcome: ${data.optString("outcome")}\nDuration: ${data.optInt("duration_seconds")} sec\nUrgency: ${data.optString("urgency")}\nCallback requested: ${data.optBoolean("callback_requested")}\n\nSUMMARY\n${data.optString("summary")}\n\nTRANSCRIPT\n$transcript")
                        .setPositiveButton("Close",null).show()
                }
            } catch(e:Exception) { runOnUiThread { Toast.makeText(this,"Could not load call details.",Toast.LENGTH_SHORT).show() } }
        }
    }

    private fun updateStatus(id:Int,value:String) {
        thread {
            try {
                val conn=authenticatedConnection("/call-receptionist/calls/$id/status?status=$value", "PATCH")
                val code=conn.responseCode
                val stream=if(code in 200..299) conn.inputStream else conn.errorStream
                stream?.close()
                conn.disconnect()
                if(code !in 200..299) throw IllegalStateException("Call update failed (HTTP $code)")
                runOnUiThread { Toast.makeText(this,"Call updated",Toast.LENGTH_SHORT).show(); loadCalls() }
            } catch(e:Exception) { runOnUiThread { Toast.makeText(this,"Could not update call status.",Toast.LENGTH_SHORT).show() } }
        }
    }

    private fun deleteCall(id:Int) {
        thread {
            try {
                val conn=authenticatedConnection("/call-receptionist/calls/$id","DELETE")
                val code=conn.responseCode
                val stream=if(code in 200..299) conn.inputStream else conn.errorStream
                stream?.close()
                conn.disconnect()
                if(code !in 200..299) throw IllegalStateException("Delete failed (HTTP $code)")
                runOnUiThread { Toast.makeText(this,"Call record deleted",Toast.LENGTH_SHORT).show(); loadCalls() }
            } catch(e:Exception) {
                runOnUiThread { Toast.makeText(this,"Could not delete call record.",Toast.LENGTH_SHORT).show() }
            }
        }
    }

    private fun notifyCallbackOrUrgent(c:JSONObject) {
        val id=c.optInt("id")
        val urgent=c.optString("urgency")=="urgent"
        val callback=c.optBoolean("callback_requested")
        if(!urgent && !callback) return
        val key="call_notice_$id"
        if(prefs.getBoolean(key,false)) return
        if(Build.VERSION.SDK_INT>=33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=android.content.pm.PackageManager.PERMISSION_GRANTED) return
        val manager=getSystemService(NotificationManager::class.java)
        val channel="cherry_call_summary"
        if(Build.VERSION.SDK_INT>=26) manager.createNotificationChannel(NotificationChannel(channel,"Call summaries and callbacks",NotificationManager.IMPORTANCE_HIGH))
        val title=if(urgent) "Urgent call needs attention" else "Callback requested"
        val text="${c.optString("caller_number","Unknown caller")}: ${c.optString("summary","").take(120)}"
        val notification=NotificationCompat.Builder(this,channel)
            .setSmallIcon(android.R.drawable.sym_action_call)
            .setContentTitle(title).setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setAutoCancel(true).build()
        manager.notify(20000+id,notification)
        prefs.edit().putBoolean(key,true).apply()
    }
}
