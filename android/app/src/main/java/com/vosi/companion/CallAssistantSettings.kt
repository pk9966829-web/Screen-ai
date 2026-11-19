package com.vosi.companion

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Phone
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
internal fun CallAssistantSettingsScreen(onBack: () -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val prefs = remember(context) { context.getSharedPreferences("vosi_call_assistant", 0) }
    var busyMode by remember { mutableStateOf(prefs.getBoolean("busy_mode", false)) }
    var autoAnswer by remember { mutableStateOf(prefs.getBoolean("auto_answer", false)) }
    var unknownCallers by remember { mutableStateOf(prefs.getBoolean("unknown_callers", false)) }
    var urgentAlerts by remember { mutableStateOf(prefs.getBoolean("urgent_alerts", true)) }
    var summaries by remember { mutableStateOf(prefs.getBoolean("summaries", true)) }
    var personalAnswers by remember { mutableStateOf(prefs.getBoolean("personal_answers", false)) }
    var greeting by remember { mutableStateOf(prefs.getString("greeting", "Hi, I'm VOSI, your AI assistant. You're unavailable right now. How can I help?") ?: "") }
    Column(Modifier.fillMaxSize().background(Color(0xF20B0B0F)).statusBarsPadding().navigationBarsPadding()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.Outlined.ArrowBack, "Back", tint = Color.White) }
            Column(Modifier.weight(1f)) {
                Text("Call Assistant", color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                Text("Busy mode & answering preferences", color = Color(0xFF9A91A1), fontSize = 11.sp)
            }
            Icon(Icons.Outlined.Phone, null, tint = Color(0xFFFF70C5), modifier = Modifier.size(24.dp))
        }
        HorizontalDivider(color = Color(0x22FFFFFF))
        Column(Modifier.fillMaxSize().padding(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Surface(color = Color(0x331F1824), shape = RoundedCornerShape(16.dp), border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x44FF70C5))) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Call automation is not connected yet", color = Color(0xFFFF80C9), fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                    Text("Preferences save locally. This build does not yet answer cellular calls or stream two-way call audio. AI auto-answer is off by default.", color = Color(0xFFD1C8D4), fontSize = 11.sp, lineHeight = 16.sp)
                }
            }
            LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp), contentPadding = PaddingValues(bottom = 6.dp)) {
                item { CallPreferenceRow("Busy mode", "Mark yourself unavailable; call integration is not active yet.", busyMode) { busyMode = it } }
                item { CallPreferenceRow("AI auto-answer", "Future feature. Disabled until a supported call audio route is verified.", autoAnswer) { autoAnswer = it } }
                item { CallPreferenceRow("Handle unknown callers", "Policy preference for a future call-answering integration.", unknownCallers) { unknownCallers = it } }
                item { CallPreferenceRow("Interrupt me for urgent calls", "Urgent calls should alert you instead of being handled silently.", urgentAlerts) { urgentAlerts = it } }
                item { CallPreferenceRow("Save call summaries", "Prepare summaries after supported calls.", summaries) { summaries = it } }
                item { CallPreferenceRow("Answer using personal details", "Use your approved profile only (off by default).", personalAnswers) { personalAnswers = it } }
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Text("AI greeting", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                        OutlinedTextField(value = greeting, onValueChange = { greeting = it }, modifier = Modifier.fillMaxWidth(), minLines = 2, maxLines = 4, placeholder = { Text("Greeting spoken to callers") }, colors = OutlinedTextFieldDefaults.colors(focusedTextColor = Color.White, unfocusedTextColor = Color.White, focusedBorderColor = Color(0xFFFF70C5), unfocusedBorderColor = Color(0x33FFFFFF), cursorColor = Color(0xFFFF70C5)))
                    }
                }
            }
            Button(onClick = {
                prefs.edit().putBoolean("busy_mode", busyMode).putBoolean("auto_answer", autoAnswer)
                    .putBoolean("unknown_callers", unknownCallers).putBoolean("urgent_alerts", urgentAlerts)
                    .putBoolean("summaries", summaries).putBoolean("personal_answers", personalAnswers)
                    .putString("greeting", greeting.trim()).apply()
            }, modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFB92A87)), shape = RoundedCornerShape(14.dp)) {
                Text("Save call preferences", color = Color.White)
            }
        }
    }
}

@Composable
private fun CallPreferenceRow(title: String, detail: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Surface(color = Color(0xFF151219), shape = RoundedCornerShape(15.dp), border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x22FFFFFF))) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 13.dp, vertical = 11.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(title, color = Color(0xFFF3EFF5), fontSize = 13.sp, fontWeight = FontWeight.Medium)
                Text(detail, color = Color(0xFF9B93A2), fontSize = 10.sp, lineHeight = 14.sp)
            }
            Switch(checked = checked, onCheckedChange = onCheckedChange)
        }
    }
}
