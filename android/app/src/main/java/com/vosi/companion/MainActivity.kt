package com.vosi.companion

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.ContactsContract
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var contactName: EditText
    private lateinit var phoneNumber: EditText
    private val contactsPermission = 100
    private val callPermission = 101

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(28, 36, 28, 28)
            gravity = Gravity.TOP
        }

        val heading = TextView(this).apply {
            text = "VOSI Companion"
            textSize = 26f
        }
        val subtitle = TextView(this).apply {
            text = "Your Android companion is installed. This first build supports contact lookup and confirmed phone calls."
            textSize = 15f
            setPadding(0, 12, 0, 24)
        }

        contactName = EditText(this).apply {
            hint = "Contact name (for example, Dad)"
            singleLine = true
        }
        phoneNumber = EditText(this).apply {
            hint = "Phone number"
            singleLine = true
            inputType = 3
        }
        status = TextView(this).apply {
            text = "Contacts are only read after you grant permission."
            textSize = 14f
            setPadding(0, 18, 0, 18)
        }

        val findButton = Button(this).apply {
            text = "Find contact"
            setOnClickListener { findContact() }
        }
        val callButton = Button(this).apply {
            text = "Call this number"
            setOnClickListener { confirmAndCall() }
        }

        root.addView(heading)
        root.addView(subtitle)
        root.addView(contactName, matchWidth())
        root.addView(findButton, matchWidth())
        root.addView(phoneNumber, matchWidth())
        root.addView(callButton, matchWidth())
        root.addView(status)
        setContentView(root)
    }

    private fun matchWidth(): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)

    private fun findContact() {
        if (checkSelfPermission(Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.READ_CONTACTS), contactsPermission)
            return
        }

        val query = contactName.text.toString().trim()
        if (query.isEmpty()) {
            status.text = "Enter a contact name first."
            return
        }

        val projection = arrayOf(
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
            ContactsContract.CommonDataKinds.Phone.NUMBER
        )
        val selection = "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} LIKE ?"
        val args = arrayOf("%$query%")

        try {
            contentResolver.query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                projection,
                selection,
                args,
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " ASC"
            )?.use { cursor ->
                if (!cursor.moveToFirst()) {
                    status.text = "No matching contact found. Check the name and try again."
                    return
                }
                val name = cursor.getString(0) ?: query
                val number = cursor.getString(1) ?: ""
                phoneNumber.setText(number)
                status.text = "Found $name. Check the number before calling."
            }
        } catch (error: SecurityException) {
            status.text = "Contacts permission was not granted."
        }
    }

    private fun confirmAndCall() {
        val number = phoneNumber.text.toString().trim()
        if (number.isEmpty()) {
            status.text = "Find a contact or enter a phone number first."
            return
        }

        AlertDialog.Builder(this)
            .setTitle("Confirm phone call")
            .setMessage("VOSI is about to call $number. Continue?")
            .setNegativeButton("Cancel", null)
            .setPositiveButton("Call") { _, _ -> placeCall(number) }
            .show()
    }

    private fun placeCall(number: String) {
        if (checkSelfPermission(Manifest.permission.CALL_PHONE) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.CALL_PHONE), callPermission)
            return
        }
        try {
            startActivity(Intent(Intent.ACTION_CALL, Uri.parse("tel:${Uri.encode(number)}")))
        } catch (error: Exception) {
            status.text = "Unable to start the call: ${error.message ?: "unknown error"}"
        }
    }

    @Deprecated("Uses Android's permission callback for broad device compatibility")
    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        val granted = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED
        when (requestCode) {
            contactsPermission -> status.text =
                if (granted) "Contacts permission granted. Tap Find contact again."
                else "Contacts permission denied. You can still enter a number manually."
            callPermission -> status.text =
                if (granted) "Call permission granted. Tap Call this number again to confirm."
                else "Call permission denied. Calling is disabled until you grant it."
        }
    }
}
