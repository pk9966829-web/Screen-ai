package com.vosi.companion

import android.app.Activity
import android.app.role.RoleManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

/**
 * User-controlled setup for Android's Call Screening role.
 * Screening provides caller metadata; it does not expose call audio or allow an app to
 * answer a normal cellular call as an AI receptionist.
 */
class CherryCallAssistantActivity : Activity() {
    private val prefs by lazy { getSharedPreferences(CherryCallScreeningService.PREFS, Context.MODE_PRIVATE) }
    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        render()
    }

    override fun onResume() {
        super.onResume()
        if (::status.isInitialized) updateStatus()
    }

    private fun render() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 48, 48, 48)
            gravity = Gravity.CENTER_HORIZONTAL
        }
        root.addView(TextView(this).apply {
            text = "CHERRY AI Call Assistant"
            textSize = 24f
        })
        root.addView(TextView(this).apply {
            text = "Set up optional incoming-call detection for your normal SIM calls. Android requires you to grant the Call Screening role."
            textSize = 16f
            setPadding(0, 24, 0, 24)
        })
        status = TextView(this).apply { textSize = 16f }
        root.addView(status)
        root.addView(Button(this).apply {
            text = "Open call history and summaries"
            setOnClickListener { startActivity(Intent(this@CherryCallAssistantActivity, CherryCallHistoryActivity::class.java)) }
        })
        root.addView(Button(this).apply {
            text = "Enable call detection"
            setOnClickListener { requestScreeningRole() }
        })
        root.addView(Button(this).apply {
            text = if (prefs.getBoolean(CherryCallScreeningService.KEY_SCREENING_ENABLED, false)) "Turn detection off" else "Turn detection on"
            setOnClickListener {
                val enabled = !prefs.getBoolean(CherryCallScreeningService.KEY_SCREENING_ENABLED, false)
                prefs.edit().putBoolean(CherryCallScreeningService.KEY_SCREENING_ENABLED, enabled).apply()
                render()
            }
        })
        root.addView(TextView(this).apply {
            text = "Call detection does not answer, record, or listen to calls. The AI receptionist uses a separate Exotel/PSTN audio connection and stays inactive until its public backend, provider credentials, and caller-consent flow are configured."
            textSize = 14f
            setPadding(0, 28, 0, 0)
        })
        setContentView(root)
        updateStatus()
    }

    private fun updateStatus() {
        val hasRole = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            getSystemService(RoleManager::class.java).isRoleHeld(RoleManager.ROLE_CALL_SCREENING)
        } else false
        status.text = "Android call-screening permission: " + (if (hasRole) "Granted" else "Not granted") +
            "\nIncoming-call detection: " +
            (if (prefs.getBoolean(CherryCallScreeningService.KEY_SCREENING_ENABLED, false)) "On" else "Off")
    }

    private fun requestScreeningRole() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            Toast.makeText(this, "Call screening requires Android 10 or later.", Toast.LENGTH_LONG).show()
            return
        }
        val roleManager = getSystemService(RoleManager::class.java)
        if (!roleManager.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)) {
            Toast.makeText(this, "Call screening is not available on this device.", Toast.LENGTH_LONG).show()
            return
        }
        if (roleManager.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)) {
            Toast.makeText(this, "CHERRY AI already has call-screening access.", Toast.LENGTH_SHORT).show()
            return
        }
        startActivityForResult(roleManager.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING), REQUEST_ROLE)
    }

    @Deprecated("Use role result callback")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_ROLE) {
            updateStatus()
            Toast.makeText(this, if (resultCode == RESULT_OK) "Call-screening access granted." else "Permission not granted.", Toast.LENGTH_SHORT).show()
        }
    }

    companion object { private const val REQUEST_ROLE = 7301 }
}
