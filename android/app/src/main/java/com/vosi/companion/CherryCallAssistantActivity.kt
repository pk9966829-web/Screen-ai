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
    private lateinit var enableButton: Button

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
            text = "Set up optional incoming-call detection for your normal SIM calls. Tap Enable and approve CHERRY AI in Android's call-screening prompt. Android returns you here automatically."
            textSize = 16f
            setPadding(0, 24, 0, 24)
        })
        status = TextView(this).apply { textSize = 16f }
        root.addView(status)
        root.addView(Button(this).apply {
            text = "Open call history and summaries"
            setOnClickListener { startActivity(Intent(this@CherryCallAssistantActivity, CherryCallHistoryActivity::class.java)) }
        })
        enableButton = Button(this).apply {
            text = "Enable call detection"
            setOnClickListener { requestScreeningRole() }
        }
        root.addView(enableButton)
        root.addView(Button(this).apply {
            text = "Turn detection off"
            setOnClickListener {
                prefs.edit().putBoolean(CherryCallScreeningService.KEY_SCREENING_ENABLED, false).apply()
                updateStatus()
                Toast.makeText(this@CherryCallAssistantActivity, "Incoming-call detection turned off.", Toast.LENGTH_SHORT).show()
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

    private fun hasScreeningRole(): Boolean {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q &&
            getSystemService(RoleManager::class.java).isRoleHeld(RoleManager.ROLE_CALL_SCREENING)
    }

    private fun updateStatus() {
        val hasRole = hasScreeningRole()
        // Granting the Android role completes the user's opt-in: enable detection automatically.
        if (hasRole) {
            prefs.edit().putBoolean(CherryCallScreeningService.KEY_SCREENING_ENABLED, true).apply()
        }
        val enabled = prefs.getBoolean(CherryCallScreeningService.KEY_SCREENING_ENABLED, false) && hasRole
        status.text = "Android call-screening permission: " + (if (hasRole) "Granted" else "Not granted") +
            "\nIncoming-call detection: " + (if (enabled) "On" else "Off")
        enableButton.text = if (hasRole) "Call-screening permission granted" else "Enable call detection"
        enableButton.isEnabled = !hasRole
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
            updateStatus()
            return
        }
        // Android displays its own role approval screen. When the user returns,
        // onResume() rechecks the role and updates the app automatically.
        startActivityForResult(roleManager.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING), REQUEST_ROLE)
    }

    @Deprecated("Use role result callback")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_ROLE) {
            updateStatus()
            if (hasScreeningRole()) {
                Toast.makeText(this, "Call-screening access granted. Detection is now on.", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(this, "Call-screening access was not granted. You can try again.", Toast.LENGTH_SHORT).show()
            }
        }
    }

    companion object { private const val REQUEST_ROLE = 7301 }
}
