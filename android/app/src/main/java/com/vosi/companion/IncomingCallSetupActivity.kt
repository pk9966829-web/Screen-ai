package com.vosi.companion

import android.app.Activity
import android.app.AlertDialog
import android.app.role.RoleManager
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/**
 * Dedicated onboarding screen for Android's user-controlled call-screening role.
 * This role exposes call metadata; it does not grant access to cellular call audio.
 */
class IncomingCallSetupActivity : Activity() {
    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(28, 28, 28, 28)
        }
        root.addView(TextView(this).apply {
            text = "VOSI incoming-call assistance"
            textSize = 24f
        })
        root.addView(TextView(this).apply {
            text = "Enable Android call screening so VOSI can detect incoming calls and show caller information. Your phone will continue ringing normally. This does not let VOSI answer calls or speak to callers."
            textSize = 16f
            setPadding(0, 18, 0, 18)
        })
        status = TextView(this).apply { textSize = 14f }
        root.addView(status)
        root.addView(Button(this).apply {
            text = "Enable call screening"
            setOnClickListener { requestScreeningRole() }
        })
        root.addView(Button(this).apply {
            text = "Refresh status"
            setOnClickListener { refreshStatus() }
        })
        setContentView(root)
        refreshStatus()
    }

    private fun requestScreeningRole() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            status.text = "Incoming-call screening requires Android 10 or newer."
            return
        }
        val roleManager = getSystemService(RoleManager::class.java)
        if (!roleManager.isRoleAvailable(RoleManager.ROLE_CALL_SCREENING)) {
            status.text = "This device does not offer Android's call-screening role."
            return
        }
        if (roleManager.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)) {
            status.text = "VOSI already has call-screening access on this phone."
            return
        }
        startActivityForResult(
            roleManager.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING),
            REQUEST_CALL_SCREENING
        )
    }

    @Deprecated("Android role result callback")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_CALL_SCREENING) refreshStatus()
    }

    private fun refreshStatus() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            status.text = "Not supported on this Android version."
            return
        }
        val roleManager = getSystemService(RoleManager::class.java)
        status.text = if (roleManager.isRoleHeld(RoleManager.ROLE_CALL_SCREENING)) {
            val prefs = getSharedPreferences("vosi_call_screening", MODE_PRIVATE)
            val number = prefs.getString("last_incoming_number", null)
            val time = prefs.getLong("last_incoming_at", 0L)
            "Call screening enabled. " + if (number.isNullOrBlank()) "Waiting for the next incoming call." else "Last detected caller: $number"
        } else {
            "Call screening is not enabled. Android will not share incoming-call details with VOSI."
        }
    }

    companion object {
        private const val REQUEST_CALL_SCREENING = 7101
    }
}
