package com.vosi.companion

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.app.role.RoleManager
import android.content.Intent
import android.os.Build
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Phone
import androidx.compose.material3.*
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
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
    val activity = context as? Activity
    val prefs = remember(context) { context.getSharedPreferences("vosi_call_assistant", 0) }
    var busyMode by remember { mutableStateOf(prefs.getBoolean("busy_mode", false)) }
    var autoAnswer by remember { mutableStateOf(prefs.getBoolean("auto_answer", false)) }
    var unknownCallers by remember { mutableStateOf(prefs.getBoolean("unknown_callers", false)) }
    var urgentAlerts by remember { mutableStateOf(prefs.getBoolean("urgent_alerts", true)) }
    var summaries by remember { mutableStateOf(prefs.getBoolean("summaries", true)) }
    var personalAnswers by remember { mutableStateOf(prefs.getBoolean("personal_answers", false)) }
    var greeting by remember { mutableStateOf(prefs.getString("greeting", "Hi, I'm VOSI, your AI assistant. You're unavailable right now. How can I help?") ?: "") }
    var callLanguage by remember { mutableStateOf(prefs.getString("call_language", "auto") ?: "auto") }
    val screeningRoleAvailable = Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q
    val roleManager = if (screeningRoleAvailable) context.getSystemService(RoleManager::class.java) else null
    var hasScreeningRole by remember { mutableStateOf(roleManager?.isRoleHeld(RoleManager.ROLE_CALL_SCREENING) == true) }
    var hasContactsAccess by remember { mutableStateOf(context.checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED) }
    val lifecycleOwner = androidx.compose.ui.platform.LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner, roleManager) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                hasScreeningRole = roleManager?.isRoleHeld(RoleManager.ROLE_CALL_SCREENING) == true
                hasContactsAccess = context.checkSelfPermission(Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    Column(Modifier.fillMaxSize().background(Color(0xF20B0B0F)).statusBarsPadding().navigationBarsPadding()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.Outlined.ArrowBack, "Back", tint = Color.White) }
            Column(Modifier.weight(1f)) {
                Text("Call Assistant", color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                Text("Call screening & answering preferences", color = Color(0xFF9A91A1), fontSize = 11.sp)
            }
            Icon(Icons.Outlined.Phone, null, tint = Color(0xFFFF70C5), modifier = Modifier.size(24.dp))
        }
        HorizontalDivider(color = Color(0x22FFFFFF))
        Column(Modifier.fillMaxSize().padding(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Surface(color = Color(0x331F1824), shape = RoundedCornerShape(16.dp), border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x44FF70C5))) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Native call screening", color = Color(0xFFFF80C9), fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                    Text("VOSI can use Android's supported screening service to silence unknown incoming callers when Busy mode is enabled. It does not answer calls or listen to call audio.", color = Color(0xFFD1C8D4), fontSize = 11.sp, lineHeight = 16.sp)
                    if (!hasContactsAccess) {
                        Button(onClick = { activity?.requestPermissions(arrayOf(Manifest.permission.READ_CONTACTS), 4503) }, modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF47304A))) {
                            Text("Allow contact verification")
                        }
                        Text("Without contact permission, VOSI fails safe and will not silence calls.", color = Color(0xFFB8ADB9), fontSize = 10.sp)
                    }
                    if (screeningRoleAvailable && !hasScreeningRole) {
                        Button(onClick = {
                            val intent = roleManager?.createRequestRoleIntent(RoleManager.ROLE_CALL_SCREENING)
                            if (intent != null) activity?.startActivityForResult(intent, 4502)
                        }, modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFB92A87))) {
                            Text("Enable VOSI call screening")
                        }
                    } else {
                        Text(if (hasScreeningRole) "Android call-screening role is granted." else "Call screening role request requires Android 10 or newer.", color = Color(0xFFB8ADB9), fontSize = 11.sp)
                    }
                }
            }
            LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp), contentPadding = PaddingValues(bottom = 6.dp)) {
                item { CallPreferenceRow("Busy mode", "Enable your unavailable policy. Screening only applies when this is on.", busyMode) { busyMode = it } }
                item { CallPreferenceRow("Silence unknown callers", "When Busy mode is on, silence unknown incoming calls; do not reject them.", unknownCallers) { unknownCallers = it } }
                item { CallPreferenceRow("AI auto-answer (not available)", "Cellular call answering and two-way audio are not implemented. This preference is kept off.", autoAnswer) { autoAnswer = it } }
                item { CallPreferenceRow("Interrupt me for urgent calls", "Urgent-call alerts are a future stage; this preference is saved only.", urgentAlerts) { urgentAlerts = it } }
                item { CallPreferenceRow("Save call summaries", "Call summaries are not active until a supported audio or carrier integration exists.", summaries) { summaries = it } }
                item { CallPreferenceRow("Answer using personal details", "Approved profile-answering is not active yet (off by default).", personalAnswers) { personalAnswers = it } }
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Call language", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                        Text("Automatic detects Hindi or Kannada from the caller's script; English is the fallback. Choose a fixed language if you prefer.", color = Color(0xFF9B93A2), fontSize = 10.sp, lineHeight = 14.sp)
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                            listOf("auto" to "Auto", "en" to "English", "hi" to "हिन्दी", "kn" to "ಕನ್ನಡ").forEach { (code, label) ->
                                FilterChip(
                                    selected = callLanguage == code,
                                    onClick = { callLanguage = code },
                                    label = { Text(label, fontSize = 10.sp) },
                                    modifier = Modifier.weight(1f),
                                    colors = FilterChipDefaults.filterChipColors(
                                        selectedContainerColor = Color(0xFF7D2865),
                                        selectedLabelColor = Color.White,
                                        labelColor = Color(0xFFD1C8D4)
                                    )
                                )
                            }
                        }
                    }
                }
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Text("AI greeting (future answering)", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                        OutlinedTextField(value = greeting, onValueChange = { greeting = it }, modifier = Modifier.fillMaxWidth(), minLines = 2, maxLines = 4, placeholder = { Text("Greeting spoken to callers") }, colors = OutlinedTextFieldDefaults.colors(focusedTextColor = Color.White, unfocusedTextColor = Color.White, focusedBorderColor = Color(0xFFFF70C5), unfocusedBorderColor = Color(0x33FFFFFF), cursorColor = Color(0xFFFF70C5)))
                    }
                }
            }
            Button(onClick = {
                prefs.edit().putBoolean("busy_mode", busyMode).putBoolean("auto_answer", autoAnswer)
                    .putBoolean("unknown_callers", unknownCallers).putBoolean("urgent_alerts", urgentAlerts)
                    .putBoolean("summaries", summaries).putBoolean("personal_answers", personalAnswers)
                    .putString("call_language", callLanguage)
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