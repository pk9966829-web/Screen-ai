package com.vosi.companion

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject

/** First-run profile setup. Optional preferences stay encrypted on this device for now. */
class PersonalIdentityActivity : Activity() {
    private lateinit var name: EditText
    private lateinit var language: EditText
    private lateinit var country: EditText
    private lateinit var currency: EditText
    private lateinit var brands: EditText
    private lateinit var budget: EditText
    private lateinit var status: TextView
    private var editing = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val saved = PersonalProfileStore.load(this)
        editing = intent.getBooleanExtra("edit_profile", false) || saved == null

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.TOP
            setPadding(28, 32, 28, 28)
        }
        root.addView(TextView(this).apply {
            text = if (editing) "Meet your VOSI" else "Your VOSI identity"
            textSize = 28f
        })
        root.addView(TextView(this).apply {
            text = "Set up your preferences once. You can skip anything and change these details later. VOSI never needs your passwords, OTPs, UPI PINs or CVVs."
            textSize = 15f
            setPadding(0, 12, 0, 20)
        })
        name = field("What should VOSI call you?", saved?.optString("display_name", "").orEmpty())
        language = field("Preferred language (e.g. English)", saved?.optString("language", "English") ?: "English")
        country = field("Country (e.g. India)", saved?.optString("country", "India") ?: "India")
        currency = field("Currency (e.g. INR)", saved?.optString("currency", "INR") ?: "INR")
        brands = field("Favourite brands (optional)", saved?.optString("preferred_brands", "").orEmpty())
        budget = field("Usual shopping budget (optional)", saved?.optString("shopping_budget", "").orEmpty())
        listOf(name, language, country, currency, brands, budget).forEach { root.addView(it, matchWidth()) }

        status = TextView(this).apply {
            text = "Your profile is encrypted with Android Keystore and stored on this phone."
            textSize = 13f
            setPadding(0, 14, 0, 10)
        }
        root.addView(status)
        root.addView(Button(this).apply {
            text = if (editing) "Save my preferences and continue" else "Open VOSI"
            setOnClickListener { saveAndContinue() }
        }, matchWidth())
        if (saved != null) {
            root.addView(Button(this).apply {
                text = "Continue without changes"
                setOnClickListener { openCompanion() }
            }, matchWidth())
            root.addView(Button(this).apply {
                text = "Delete my saved profile"
                setOnClickListener {
                    PersonalProfileStore.clear(this@PersonalIdentityActivity)
                    status.text = "Saved profile deleted from this phone."
                    name.text.clear(); brands.text.clear(); budget.text.clear()
                }
            }, matchWidth())
        }
        setContentView(ScrollView(this).apply { isFillViewport = true; addView(root) })
    }

    private fun field(hintText: String, value: String): EditText =
        EditText(this).apply {
            hint = hintText
            setText(value)
            isSingleLine = true
            textSize = 16f
        }

    private fun matchWidth() = LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT
    )

    private fun saveAndContinue() {
        val profile = JSONObject()
            .put("display_name", name.text.toString().trim().take(80))
            .put("language", language.text.toString().trim().take(40).ifBlank { "English" })
            .put("country", country.text.toString().trim().take(80).ifBlank { "India" })
            .put("currency", currency.text.toString().trim().take(8).ifBlank { "INR" })
            .put("preferred_brands", brands.text.toString().trim().take(500))
            .put("shopping_budget", budget.text.toString().trim().take(100))
            .put("profile_version", 1)
        PersonalProfileStore.save(this, profile)
        openCompanion()
    }

    private fun openCompanion() {
        startActivity(Intent(this, MainActivity::class.java))
        finish()
    }
}
