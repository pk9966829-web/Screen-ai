package com.vosi.companion

import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/** Shared visual treatment for the remaining legacy Android companion workspaces. */
object VosiLegacyTheme {
    private val ink = Color.rgb(8, 10, 18)
    private val panel = Color.rgb(20, 24, 39)
    private val accent = Color.rgb(182, 156, 255)
    private val cyan = Color.rgb(98, 217, 245)
    private val text = Color.rgb(245, 247, 255)
    private val muted = Color.rgb(155, 165, 188)

    fun apply(root: LinearLayout, scroll: ScrollView) {
        root.background = GradientDrawable(
            GradientDrawable.Orientation.TL_BR,
            intArrayOf(Color.rgb(17, 21, 42), ink, ink)
        )
        root.setPadding(22, 24, 22, 28)
        scroll.setBackgroundColor(ink)
        for (index in 0 until root.childCount) {
            val view = root.getChildAt(index)
            when (view) {
                is Button -> {
                    view.isAllCaps = false
                    view.textSize = 14f
                    view.typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
                    view.setTextColor(Color.rgb(12, 13, 24))
                    view.background = rounded(
                        intArrayOf(accent, cyan),
                        48f,
                        Color.TRANSPARENT
                    )
                    view.setPadding(18, 13, 18, 13)
                    (view.layoutParams as? LinearLayout.LayoutParams)?.let {
                        it.topMargin = 5
                        it.bottomMargin = 7
                        view.layoutParams = it
                    }
                }
                is EditText -> {
                    view.textSize = 14f
                    view.setTextColor(text)
                    view.setHintTextColor(muted)
                    view.background = rounded(intArrayOf(panel, panel), 18f, Color.rgb(57, 66, 94))
                    view.setPadding(16, 14, 16, 14)
                    (view.layoutParams as? LinearLayout.LayoutParams)?.let {
                        it.topMargin = 5
                        it.bottomMargin = 8
                        view.layoutParams = it
                    }
                }
                is TextView -> {
                    val label = view.text?.toString().orEmpty()
                    val isSection = label == label.uppercase() && label.length in 3..30
                    view.setTextColor(if (isSection) accent else text)
                    view.textSize = if (isSection) 11f else 13f
                    if (isSection) {
                        view.typeface = Typeface.create("sans-serif-medium", Typeface.BOLD)
                        view.letterSpacing = 0.12f
                    }
                }
            }
        }
    }

    private fun rounded(colors: IntArray, radius: Float, stroke: Int): GradientDrawable =
        GradientDrawable(GradientDrawable.Orientation.LEFT_RIGHT, colors).apply {
            cornerRadius = radius
            if (stroke != Color.TRANSPARENT) setStroke(1, stroke)
        }
}
