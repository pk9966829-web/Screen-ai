package com.vosi.companion

import android.Manifest
import android.content.pm.PackageManager
import android.telecom.Call
import android.telecom.CallScreeningService

/**
 * Native Android call screening only. This service does not answer calls or access call audio.
 * Silencing is fail-safe: only when contact access is granted and the caller is not a contact.
 */
class VosiCallScreeningService : CallScreeningService() {
    override fun onScreenCall(callDetails: Call.Details) {
        val incoming = callDetails.callDirection == Call.Details.DIRECTION_INCOMING
        val prefs = getSharedPreferences("vosi_call_assistant", MODE_PRIVATE)
        val busyMode = prefs.getBoolean("busy_mode", false)
        val screenUnknown = prefs.getBoolean("unknown_callers", false)
        val hasContactsAccess = checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED
        val contactName = callDetails.contactDisplayName?.trim().orEmpty()
        val isKnownContact = contactName.isNotEmpty()

        // Never silence callers if contact access is unavailable; trusted callers cannot be verified.
        val silence = incoming && busyMode && screenUnknown && hasContactsAccess && !isKnownContact
        val response = CallResponse.Builder()
            .setDisallowCall(false)
            .setRejectCall(false)
            .setSkipCallLog(false)
            .setSkipNotification(false)
            .setSilenceCall(silence)
            .build()

        respondToCall(callDetails, response)
    }
}