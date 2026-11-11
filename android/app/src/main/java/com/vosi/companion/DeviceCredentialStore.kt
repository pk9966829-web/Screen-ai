package com.vosi.companion

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import org.json.JSONObject
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Encrypts the VOSI device credential with an AES key held by Android Keystore.
 * Only ciphertext and the GCM IV are stored in app-private preferences.
 */
object DeviceCredentialStore {
    private const val KEY_ALIAS = "vosi_device_credential_v1"
    private const val PREFS = "vosi_device_secure_state"
    private const val CIPHERTEXT = "credential_ciphertext"
    private const val IV = "credential_iv"

    fun save(context: Context, credentialJson: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
        val encrypted = cipher.doFinal(credentialJson.toByteArray(Charsets.UTF_8))
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(IV, Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .putString(CIPHERTEXT, Base64.encodeToString(encrypted, Base64.NO_WRAP))
            .apply()
    }

    fun load(context: Context): JSONObject? {
        val preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val ivText = preferences.getString(IV, null) ?: return null
        val encryptedText = preferences.getString(CIPHERTEXT, null) ?: return null
        return try {
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            val iv = Base64.decode(ivText, Base64.NO_WRAP)
            val encrypted = Base64.decode(encryptedText, Base64.NO_WRAP)
            cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), GCMParameterSpec(128, iv))
            JSONObject(String(cipher.doFinal(encrypted), Charsets.UTF_8))
        } catch (_: Exception) {
            null
        }
    }

    fun clear(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().apply()
    }

    private fun getOrCreateKey(): SecretKey {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val existing = keyStore.getKey(KEY_ALIAS, null) as? SecretKey
        if (existing != null) return existing

        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        val specification = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setRandomizedEncryptionRequired(true)
            .build()
        generator.init(specification)
        return generator.generateKey()
    }
}
