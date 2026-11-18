package com.vosi.companion

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import kotlin.concurrent.thread

private val Ink = Color(0xFF0B0B0F)
private val Panel = Color(0xFF151219)
private val Soft = Color(0xFF211A25)
private val Accent = Color(0xFFFF3FB4)
private val GlowBlue = Color(0xFFB44CFF)
private val Muted = Color(0xFF9BA5BC)
private val BorderGlow = Color(0x334E5E9B)

class VosiAppActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        VosiSessionContext.app = applicationContext
        window.statusBarColor = android.graphics.Color.rgb(11, 11, 15)
        window.navigationBarColor = android.graphics.Color.rgb(11, 11, 15)
        setContent {
            MaterialTheme(
                colorScheme = darkColorScheme(
                    primary = Accent, onPrimary = Ink, background = Ink, surface = Panel,
                    onBackground = Color.White, onSurface = Color.White, secondary = GlowBlue,
                    surfaceVariant = Soft, onSurfaceVariant = Muted
                )
            ) {
                VosiMobileRoot(
                    onOpenCompanion = { startActivity(Intent(this, MainActivity::class.java)) },
                    onOpenProfileSetup = { startActivity(Intent(this, PersonalIdentityActivity::class.java)) }
                )
            }
        }
    }
}

private enum class VosiTab(val label: String) { HOME("Home"), CHAT("Chat"), TASKS("Tasks"), DEVICES("Devices"), PROFILE("Profile") }

@Composable
private fun VosiMobileRoot(onOpenCompanion: () -> Unit, onOpenProfileSetup: () -> Unit) {
    var tab by remember { mutableStateOf(VosiTab.HOME) }
    var backend by remember { mutableStateOf("http://127.0.0.1:8001") }
    var accountEmail by remember { mutableStateOf(AccountSessionStore.email().orEmpty()) }
    var accountStatus by remember { mutableStateOf("Sign in to connect your VOSI identity across devices.") }
    var accountBusy by remember { mutableStateOf(false) }
    var authMode by remember { mutableStateOf("Sign in") }
    var password by remember { mutableStateOf("") }
    var verificationCode by remember { mutableStateOf("") }
    var loggedIn by remember { mutableStateOf(AccountSessionStore.load() != null) }
    var showServerSettings by remember { mutableStateOf(false) }
    var settingsOpen by remember { mutableStateOf(false) }
    var settingsSection by remember { mutableStateOf<VosiSettingSection?>(null) }
    var settingsSearch by remember { mutableStateOf("") }
    var chatDraft by remember { mutableStateOf("") }
    val context = LocalContext.current

    Box(Modifier.fillMaxSize()) {
        VosiAmbientBackground()
        Scaffold(containerColor = Color.Transparent) { padding ->
            Box(Modifier.fillMaxSize().padding(padding)) {
                when (tab) {
                    VosiTab.HOME -> HomeScreen(
                        onSearch = { query -> chatDraft = query; tab = VosiTab.CHAT },
                        onTalk = onOpenCompanion,
                        onOpenSettings = { settingsOpen = true }
                    )
                    VosiTab.CHAT -> SharedCompanionChatScreen(initialDraft = chatDraft)
                    VosiTab.TASKS -> TasksScreen()
                    VosiTab.DEVICES -> DevicesScreen(onOpenCompanion)
                    VosiTab.PROFILE -> ProfileScreen(
                        loggedIn, accountEmail, accountStatus, accountBusy, authMode, password,
                        verificationCode, backend, showServerSettings,
                        onEmail = { accountEmail = it }, onPassword = { password = it },
                        onCode = { verificationCode = it }, onBackend = { backend = it },
                        onMode = { authMode = it }, onToggleServer = { showServerSettings = !showServerSettings },
                        onProfileSetup = onOpenProfileSetup,
                        onLogout = {
                            val token = AccountSessionStore.load()
                            if (token != null) thread {
                                try { identityRequest(backend, "/identity/logout", "POST", token, JSONObject()) }
                                catch (_: Exception) { }
                                finally { AccountSessionStore.clear() }
                            }
                            loggedIn = false
                            accountStatus = "You are signed out."
                        },
                        onSubmit = {
                            if (accountBusy) return@ProfileScreen
                            accountBusy = true
                            accountStatus = "Connecting securely to VOSI…"
                            val email = accountEmail.trim()
                            val pass = password
                            val code = verificationCode.trim()
                            val mode = authMode
                            val base = backend.trim().trimEnd('/')
                            thread {
                                try {
                                    val result = when (mode) {
                                        "Create account" -> identityRequest(base, "/identity/register", "POST", null,
                                            JSONObject().put("email", email).put("password", pass))
                                        "Verify email" -> identityRequest(base, "/identity/verify-email", "POST", null,
                                            JSONObject().put("email", email).put("code", code))
                                        else -> identityRequest(base, "/identity/login", "POST", null,
                                            JSONObject().put("email", email).put("password", pass))
                                    }
                                    val message = result.optString("message",
                                        if (mode == "Sign in") "Signed in successfully." else "Request completed.")
                                    val token = result.optString("access_token")
                                    if (token.isNotBlank()) AccountSessionStore.save(token, email)
                                    android.os.Handler(android.os.Looper.getMainLooper()).post {
                                        if (token.isNotBlank()) loggedIn = true
                                        accountStatus = message
                                        if (mode == "Create account") authMode = "Verify email"
                                        if (mode == "Verify email") authMode = "Sign in"
                                        accountBusy = false
                                    }
                                } catch (e: Exception) {
                                    android.os.Handler(android.os.Looper.getMainLooper()).post {
                                        accountStatus = e.message ?: "Could not connect to VOSI."
                                        accountBusy = false
                                    }
                                }
                            }
                        }
                    )
                }
            }
        }

        if (tab != VosiTab.HOME && settingsSection == null && !settingsOpen) {
            Surface(
                modifier = Modifier.align(Alignment.CenterStart).width(27.dp).height(58.dp)
                    .clickable { settingsOpen = true },
                color = Color(0xCC211722),
                shape = RoundedCornerShape(topEnd = 14.dp, bottomEnd = 14.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x55FF55B7))
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(Icons.Outlined.ChevronRight, "Open VOSI navigation", tint = Color(0xFFFF70C5), modifier = Modifier.size(20.dp))
                }
            }
        }

        if (settingsOpen) {
            VosiSettingsDrawer(
                search = settingsSearch,
                onSearch = { settingsSearch = it },
                onSelect = { section -> settingsSection = section; settingsOpen = false },
                onNavigate = { destination ->
                    tab = when (destination) {
                        "chat" -> VosiTab.CHAT
                        "tasks" -> VosiTab.TASKS
                        "devices" -> VosiTab.DEVICES
                        else -> VosiTab.HOME
                    }
                    settingsOpen = false
                },
                onClose = { settingsOpen = false }
            )
        }

        val selectedSettings = settingsSection
        if (selectedSettings != null) {
            VosiSettingsDetailScreen(
                section = selectedSettings,
                onBack = { settingsSection = null; settingsOpen = true },
                onAction = { action ->
                    when (action) {
                        "profile" -> { settingsSection = null; tab = VosiTab.PROFILE }
                        "backend" -> { settingsSection = null; showServerSettings = true; tab = VosiTab.PROFILE }
                        "chat" -> { settingsSection = null; tab = VosiTab.CHAT }
                        "tasks" -> { settingsSection = null; tab = VosiTab.TASKS }
                        "devices" -> { settingsSection = null; tab = VosiTab.DEVICES }
                        "companion" -> onOpenCompanion()
                        "notifications" -> try {
                            context.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                                .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName))
                        } catch (_: Exception) {
                            Toast.makeText(context, "Open Android Settings to manage VOSI notifications.", Toast.LENGTH_SHORT).show()
                        }
                        "notification-access" -> try {
                            context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
                        } catch (_: Exception) {
                            Toast.makeText(context, "Notification access settings are unavailable on this device.", Toast.LENGTH_SHORT).show()
                        }
                        "app-settings" -> try {
                            context.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}")))
                        } catch (_: Exception) {
                            Toast.makeText(context, "Could not open Android app settings.", Toast.LENGTH_SHORT).show()
                        }
                        "language-info" -> try {
                            context.startActivity(Intent(Settings.ACTION_APP_LOCALE_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName))
                        } catch (_: Exception) {
                            Toast.makeText(context, "VOSI currently follows your Android system language.", Toast.LENGTH_SHORT).show()
                        }
                        "appearance-info" -> Toast.makeText(context, "VOSI is using its signature dark appearance.", Toast.LENGTH_SHORT).show()
                        "model-info" -> Toast.makeText(context, "AI model and provider routing are managed by the connected VOSI backend.", Toast.LENGTH_LONG).show()
                        "connector-info" -> Toast.makeText(context, "This connector is not connected. OAuth authorization must be enabled by the VOSI backend first.", Toast.LENGTH_LONG).show()
                        "screen-info" -> Toast.makeText(context, "Android screen observation is not enabled in this build yet. No screen is being captured.", Toast.LENGTH_LONG).show()
                        "about-info" -> Toast.makeText(context, "VOSI support and documentation links are not configured in this build yet.", Toast.LENGTH_LONG).show()
                    }
                }
            )
        }
    }
}

@Composable
private fun DrawerEntry(label: String, icon: androidx.compose.ui.graphics.vector.ImageVector, onClick: () -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        color = Color(0x661B2A40),
        shape = RoundedCornerShape(14.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x2238BDF8))
    ) {
        Row(Modifier.padding(horizontal = 14.dp, vertical = 15.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null, tint = GlowBlue, modifier = Modifier.size(21.dp))
            Spacer(Modifier.width(12.dp))
            Text(label, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Medium)
        }
    }
}

@Composable
private fun VosiAmbientBackground() {
    // Native Compose recreation of the supplied Android HTML's pink/purple blurred blobs.
    // The shorter cycles make the ambient motion visible without becoming distracting.
    val motion = rememberInfiniteTransition(label = "vosi-html-ambient")
    val pinkDrift by motion.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(4200), repeatMode = RepeatMode.Reverse),
        label = "pink-blob-drift"
    )
    val purpleDrift by motion.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(5200), repeatMode = RepeatMode.Reverse),
        label = "purple-blob-drift"
    )
    val lightDrift by motion.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(3400), repeatMode = RepeatMode.Reverse),
        label = "light-pink-blob-drift"
    )

    Box(Modifier.fillMaxSize().background(Color(0xFF0B0B0F))) {
        Box(
            Modifier.align(Alignment.TopStart).offset(x = (-150).dp, y = (-190).dp)
                .size(430.dp)
                .graphicsLayer {
                    translationX = pinkDrift * 74.dp.toPx()
                    translationY = pinkDrift * 40.dp.toPx()
                    scaleX = 1f + pinkDrift * 0.18f
                    scaleY = 1f + pinkDrift * 0.18f
                }
                .background(
                    Brush.radialGradient(
                        0f to Color(0xCCFF2F9E),
                        0.42f to Color(0x77FF2F9E),
                        0.78f to Color(0x22FF2F9E),
                        1f to Color.Transparent
                    )
                )
        )
        Box(
            Modifier.align(Alignment.TopEnd).offset(x = 135.dp, y = (-160).dp)
                .size(390.dp)
                .graphicsLayer {
                    translationX = -purpleDrift * 64.dp.toPx()
                    translationY = purpleDrift * 30.dp.toPx()
                    scaleX = 1f - purpleDrift * 0.10f
                    scaleY = 1f - purpleDrift * 0.10f
                }
                .background(
                    Brush.radialGradient(
                        0f to Color(0xCCA44BFF),
                        0.44f to Color(0x77A44BFF),
                        0.8f to Color(0x22A44BFF),
                        1f to Color.Transparent
                    )
                )
        )
        Box(
            Modifier.align(Alignment.TopCenter).offset(x = 8.dp, y = (-75).dp)
                .size(245.dp)
                .graphicsLayer {
                    translationX = lightDrift * 26.dp.toPx()
                    translationY = -lightDrift * 22.dp.toPx()
                    scaleX = 1f + lightDrift * 0.22f
                    scaleY = 1f + lightDrift * 0.22f
                    alpha = 0.78f
                }
                .background(
                    Brush.radialGradient(
                        0f to Color(0xBBFF77C8),
                        0.48f to Color(0x66FF77C8),
                        1f to Color.Transparent
                    )
                )
        )
        // Fade the glow into the same near-black base used by the HTML prototype.
        Box(
            Modifier.fillMaxWidth().height(390.dp).align(Alignment.TopCenter)
                .background(
                    Brush.verticalGradient(
                        0f to Color.Transparent,
                        0.42f to Color(0x220B0B0F),
                        0.78f to Color(0xCC0B0B0F),
                        1f to Color(0xFF0B0B0F)
                    )
                )
        )
    }
}

@Composable
private fun HomeScreen(
    onSearch: (String) -> Unit,
    onTalk: () -> Unit,
    onOpenSettings: () -> Unit
) {
    var query by remember { mutableStateOf("") }
    var connectorsOpen by remember { mutableStateOf(false) }

    Box(Modifier.fillMaxSize()) {
        IconButton(
            onClick = onOpenSettings,
            modifier = Modifier.align(Alignment.TopStart).padding(start = 13.dp, top = 10.dp)
                .size(44.dp)
                .background(Color(0x99191420), RoundedCornerShape(15.dp))
        ) {
            Icon(Icons.Outlined.Menu, "Open navigation and settings", tint = Color.White, modifier = Modifier.size(23.dp))
        }

        Column(
            Modifier.align(Alignment.Center).fillMaxWidth().padding(horizontal = 21.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Hi, I'm ", color = Color.White, fontSize = 31.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.7).sp)
                Text(
                    "VOSI",
                    style = androidx.compose.ui.text.TextStyle(
                        brush = Brush.horizontalGradient(listOf(Color(0xFFFF3FB4), Color(0xFFB44CFF))),
                        fontSize = 31.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = (-0.7).sp
                    )
                )
            }
            Spacer(Modifier.height(48.dp))
            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = Color(0xE6131118),
                shape = RoundedCornerShape(28.dp),
                border = androidx.compose.foundation.BorderStroke(
                    1.dp,
                    Brush.linearGradient(listOf(Color(0xFFFF3FB4), Color(0xFFB44CFF)))
                ),
                shadowElevation = 13.dp
            ) {
                Row(
                    Modifier.padding(start = 8.dp, end = 8.dp, top = 7.dp, bottom = 7.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(onClick = { connectorsOpen = true }, modifier = Modifier.size(42.dp)) {
                        CubeConnectorMark()
                    }
                    androidx.compose.foundation.text.BasicTextField(
                        value = query,
                        onValueChange = { query = it },
                        modifier = Modifier.weight(1f).padding(horizontal = 4.dp),
                        singleLine = true,
                        textStyle = androidx.compose.ui.text.TextStyle(
                            color = Color.White,
                            fontSize = 15.sp
                        ),
                        cursorBrush = androidx.compose.ui.graphics.SolidColor(Color(0xFFFF65BE)),
                        keyboardOptions = KeyboardOptions(imeAction = androidx.compose.ui.text.input.ImeAction.Send),
                        keyboardActions = KeyboardActions(onSend = {
                            if (query.isNotBlank()) {
                                val message = query.trim()
                                query = ""
                                onSearch(message)
                            }
                        }),
                        decorationBox = { inner ->
                            Box {
                                if (query.isBlank()) {
                                    Text("Ask VOSI anything…", color = Color(0xFF8A8798), fontSize = 15.sp)
                                }
                                inner()
                            }
                        }
                    )
                    IconButton(onClick = onTalk, modifier = Modifier.size(40.dp)) {
                        Icon(Icons.Outlined.Mic, "Voice input", tint = Color(0xFFE9D9EE), modifier = Modifier.size(22.dp))
                    }
                    FilledIconButton(
                        onClick = {
                            if (query.isNotBlank()) {
                                val message = query.trim()
                                query = ""
                                onSearch(message)
                            }
                        },
                        enabled = query.isNotBlank(),
                        modifier = Modifier.size(38.dp),
                        colors = IconButtonDefaults.filledIconButtonColors(
                            containerColor = Color(0xFFFF4EAE),
                            contentColor = Color.White,
                            disabledContainerColor = Color(0xFF332532),
                            disabledContentColor = Color(0xFF756A78)
                        )
                    ) {
                        Icon(Icons.Outlined.ArrowUpward, "Send to VOSI", modifier = Modifier.size(19.dp))
                    }
                }
            }
        }
    }

    if (connectorsOpen) {
        AlertDialog(
            onDismissRequest = { connectorsOpen = false },
            containerColor = Color(0xFF151119),
            title = { Text("VOSI Connectors", color = Color.White, fontWeight = FontWeight.Bold) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Connect services to let VOSI work across your apps.", color = Muted, fontSize = 12.sp)
                    listOf(
                        "Gmail" to "Email",
                        "Google services" to "Calendar, Drive and Contacts",
                        "Browser integration" to "Browser pages and search",
                        "Chrome extension" to "Desktop browser companion",
                        "Third-party apps" to "Authorized integrations"
                    ).forEach { (name, detail) ->
                        Row(
                            Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(name, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                                Text(detail, color = Muted, fontSize = 10.sp)
                            }
                            Text("Not connected", color = Color(0xFFE8A0C5), fontSize = 10.sp)
                        }
                    }
                    Text(
                        "No connector will be shown as connected until its real OAuth or pairing flow succeeds.",
                        color = Color(0xFF9C91A0),
                        fontSize = 10.sp,
                        lineHeight = 14.sp
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = { connectorsOpen = false }) { Text("Close", color = Color(0xFFFF70C5)) }
            }
        )
    }
}

@Composable
private fun CubeConnectorMark() {
    androidx.compose.foundation.Canvas(Modifier.size(23.dp)) {
        val w = size.width
        val h = size.height
        val stroke = androidx.compose.ui.graphics.drawscope.Stroke(width = 1.9.dp.toPx())
        val outline = androidx.compose.ui.graphics.Path().apply {
            moveTo(w * 0.5f, h * 0.08f)
            lineTo(w * 0.9f, h * 0.29f)
            lineTo(w * 0.9f, h * 0.71f)
            lineTo(w * 0.5f, h * 0.93f)
            lineTo(w * 0.1f, h * 0.71f)
            lineTo(w * 0.1f, h * 0.29f)
            close()
        }
        drawPath(outline, Color(0xFFFF70C5), style = stroke)
        drawLine(Color(0xFFFF70C5), Offset(w * 0.5f, h * 0.08f), Offset(w * 0.5f, h * 0.5f), strokeWidth = stroke.width)
        drawLine(Color(0xFFFF70C5), Offset(w * 0.1f, h * 0.29f), Offset(w * 0.5f, h * 0.5f), strokeWidth = stroke.width)
        drawLine(Color(0xFFFF70C5), Offset(w * 0.9f, h * 0.29f), Offset(w * 0.5f, h * 0.5f), strokeWidth = stroke.width)
        drawLine(Color(0xFFFF70C5), Offset(w * 0.5f, h * 0.5f), Offset(w * 0.5f, h * 0.93f), strokeWidth = stroke.width)
    }
}

@Composable
private fun ActionCard(title: String, detail: String, icon: androidx.compose.ui.graphics.vector.ImageVector, modifier: Modifier, onClick: () -> Unit) {
    Surface(modifier.clickable(onClick = onClick), color = Panel, shape = RoundedCornerShape(22.dp), border = androidx.compose.foundation.BorderStroke(1.dp, BorderGlow)) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null, tint = Accent, modifier = Modifier.size(24.dp))
            Spacer(Modifier.width(12.dp))
            Column {
                Text(title, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                Text(detail, fontSize = 11.sp, color = Muted)
            }
        }
    }
}

@Composable
private fun PageHeader(title: String, subtitle: String) {
    Column(Modifier.padding(bottom = 10.dp)) {
        Text(title, fontSize = 27.sp, fontWeight = FontWeight.Bold, letterSpacing = (-.5).sp)
        Spacer(Modifier.height(5.dp))
        Text(subtitle, color = Muted, fontSize = 13.sp)
    }
}

@Composable
private fun ChatScreen(onOpenCompanion: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(22.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        PageHeader("Talk to VOSI", "A companion that can help across your devices.")
        Surface(color = Panel, shape = RoundedCornerShape(22.dp), modifier = Modifier.fillMaxWidth().weight(1f)) {
            Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text("VOSI", color = Accent, fontWeight = FontWeight.Bold)
                Text("Hello! I'm here. You can speak with me, ask a question, or give me a task.", fontSize = 16.sp)
                Text("Your existing companion voice and task tools are ready to open.", color = Muted, fontSize = 12.sp)
                Spacer(Modifier.weight(1f))
                Text("Voice and live conversation open in the companion workspace.", color = Muted, fontSize = 12.sp)
            }
        }
        Button(onClick = onOpenCompanion, modifier = Modifier.fillMaxWidth().height(54.dp), shape = RoundedCornerShape(18.dp)) {
            Icon(Icons.Outlined.Mic, null); Spacer(Modifier.width(9.dp)); Text("Open voice & companion workspace")
        }
        Text("A full in-app AI chat composer and synced conversation history will be added in the next integration milestone.", color = Muted, fontSize = 11.sp)
    }
}

@Composable
private fun TasksScreen() {
    val context = LocalContext.current
    var tasks by remember { mutableStateOf(listOf<JSONObject>()) }
    var approvals by remember { mutableStateOf(listOf<JSONObject>()) }
    var status by remember { mutableStateOf("Connect your paired phone to load task activity.") }
    var busy by remember { mutableStateOf(false) }

    fun refreshTasks() {
        if (busy) return
        busy = true
        status = "Syncing your task activity…"
        thread {
            try {
                val credential = DeviceCredentialStore.load(context)
                    ?: throw IllegalStateException("Pair this phone with VOSI to view its tasks and approvals.")
                val base = credential.optString("backend_url").trimEnd('/')
                val token = credential.optString("device_token")
                val updateResponse = identityRequest(base, "/agent/tasks/updates", "GET", token, JSONObject())
                val approvalResponse = identityRequest(base, "/agent/tasks/pending-approvals", "GET", token, JSONObject())
                val taskArray = updateResponse.optJSONArray("updates") ?: org.json.JSONArray()
                val approvalArray = approvalResponse.optJSONArray("approvals") ?: org.json.JSONArray()
                val taskItems = (0 until taskArray.length()).mapNotNull { taskArray.optJSONObject(it) }
                val approvalItems = (0 until approvalArray.length()).mapNotNull { approvalArray.optJSONObject(it) }
                android.os.Handler(android.os.Looper.getMainLooper()).post {
                    tasks = taskItems
                    approvals = approvalItems
                    status = if (taskItems.isEmpty()) "No tasks requested from this phone yet."
                        else "Updated just now · ${taskItems.size} task(s)"
                    busy = false
                }
            } catch (error: Exception) {
                android.os.Handler(android.os.Looper.getMainLooper()).post {
                    status = error.message ?: "Could not load VOSI task activity."
                    busy = false
                }
            }
        }
    }

    fun respondToApproval(approval: JSONObject, approve: Boolean) {
        if (busy) return
        busy = true
        status = if (approve) "Sending your approval…" else "Declining this action…"
        val taskId = approval.optString("task_id")
        val stepId = approval.optString("step_id")
        val digest = approval.optString("confirmation_digest")
        thread {
            try {
                val credential = DeviceCredentialStore.load(context)
                    ?: throw IllegalStateException("Pair this phone with VOSI first.")
                val base = credential.optString("backend_url").trimEnd('/')
                val token = credential.optString("device_token")
                val path = if (approve) {
                    "/agent/tasks/${taskId}/steps/${stepId}/approve-origin"
                } else {
                    "/agent/tasks/${taskId}/steps/${stepId}/reject-origin"
                }
                val body = if (approve) JSONObject().put("confirmation_digest", digest) else JSONObject()
                identityRequest(base, path, "POST", token, body)
                android.os.Handler(android.os.Looper.getMainLooper()).post {
                    busy = false
                    status = if (approve) "Approval recorded. VOSI can continue with the approved step."
                        else "You declined the action. The task was stopped."
                    refreshTasks()
                }
            } catch (error: Exception) {
                android.os.Handler(android.os.Looper.getMainLooper()).post {
                    status = error.message ?: "Could not submit your decision."
                    busy = false
                }
            }
        }
    }

    LaunchedEffect(Unit) { refreshTasks() }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(22.dp),
        verticalArrangement = Arrangement.spacedBy(13.dp)
    ) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                PageHeader("Your activity", "Follow what VOSI is doing for you.")
                TextButton(onClick = { refreshTasks() }, enabled = !busy) {
                    if (busy) CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Outlined.Refresh, "Refresh", tint = Accent)
                }
            }
            Text(status, color = Muted, fontSize = 12.sp)
        }
        if (approvals.isNotEmpty()) {
            item { Text("WAITING FOR YOUR APPROVAL", color = Accent, fontSize = 11.sp, fontWeight = FontWeight.Bold) }
            items(approvals.size) { index ->
                val approval = approvals[index]
                Surface(color = Panel, shape = RoundedCornerShape(22.dp), border = androidx.compose.foundation.BorderStroke(1.dp, BorderGlow), modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                        Text(approval.optString("goal", "VOSI needs your approval"), fontWeight = FontWeight.SemiBold)
                        Text(approval.optString("title", "Review this action"), color = Muted, fontSize = 12.sp)
                        val summary = approval.optJSONObject("arguments")?.optJSONObject("checkout_summary")
                        if (summary != null) {
                            Text("Merchant: ${summary.optString("merchant")}", fontSize = 12.sp)
                            Text("Total: ${summary.optString("currency")} ${summary.optString("total")}", fontSize = 12.sp)
                            Text("Items: ${summary.optJSONArray("items")?.toString() ?: "Not provided"}", fontSize = 12.sp)
                            Text("Delivery: ${summary.optString("delivery_address")}", fontSize = 12.sp)
                            Text("Payment method: ${summary.optString("payment_method")}", fontSize = 12.sp)
                        }
                        Text("Review the exact details before approving. Approval applies only to this checkout snapshot.", color = Muted, fontSize = 11.sp)
                        Row(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                            Button(onClick = { respondToApproval(approval, true) }, enabled = !busy, modifier = Modifier.weight(1f)) { Text("Approve") }
                            OutlinedButton(onClick = { respondToApproval(approval, false) }, enabled = !busy, modifier = Modifier.weight(1f)) { Text("Decline") }
                        }
                    }
                }
            }
        }
        item { Text("TASK HISTORY", color = Muted, fontSize = 11.sp, fontWeight = FontWeight.Bold) }
        if (tasks.isEmpty()) {
            item { InfoTile(Icons.Outlined.PendingActions, "No task history yet", "When you ask VOSI to perform a task from this phone, its progress and verified result will appear here.") }
        } else {
            items(tasks.size) { index ->
                val task = tasks[index]
                val progress = task.optJSONObject("progress")
                val percent = progress?.optInt("percent", 0)?.coerceIn(0, 100) ?: 0
                val current = task.optJSONObject("current_step")
                val next = task.optJSONObject("next_step")
                Surface(color = Panel, shape = RoundedCornerShape(20.dp), modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                            Text(task.optString("state", "planned").replaceFirstChar { it.uppercase() }, color = Accent, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                            Text("${progress?.optInt("completed", 0) ?: 0}/${progress?.optInt("total", 0) ?: 0} steps", color = Muted, fontSize = 11.sp)
                        }
                        Text(task.optString("goal", "VOSI task"), fontWeight = FontWeight.SemiBold)
                        LinearProgressIndicator(progress = percent / 100f, modifier = Modifier.fillMaxWidth())
                        Text("${percent}% complete", color = Muted, fontSize = 11.sp)
                        if (current != null) Text("Running: ${current.optString("title")}", fontSize = 12.sp)
                        else if (next != null) Text("Next: ${next.optString("title")}", fontSize = 12.sp)
                        if (task.optBoolean("waiting_for_approval")) Text("Waiting for your approval", color = Accent, fontSize = 12.sp)
                        if (task.optString("error").isNotBlank()) Text(task.optString("error"), color = Color(0xFFFF9B9B), fontSize = 12.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun DevicesScreen(onOpenCompanion: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(22.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        PageHeader("Your devices", "Bring your digital world together.")
        InfoTile(Icons.Outlined.PhoneAndroid, "This Android phone", "Pair this phone securely with your VOSI backend.")
        InfoTile(Icons.Outlined.Computer, "Windows computer", "Send tasks to your paired desktop and receive completion updates.")
        InfoTile(Icons.Outlined.Language, "Browser", "Connect the VOSI browser companion for supported page and product tasks.")
        Button(onClick = onOpenCompanion, modifier = Modifier.fillMaxWidth().height(52.dp), shape = RoundedCornerShape(16.dp)) {
            Icon(Icons.Outlined.Link, null); Spacer(Modifier.width(8.dp)); Text("Open device pairing & controls")
        }
    }
}

@Composable
private fun InfoTile(icon: androidx.compose.ui.graphics.vector.ImageVector, title: String, detail: String) {
    Surface(color = Panel, shape = RoundedCornerShape(20.dp), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(17.dp), verticalAlignment = Alignment.Top) {
            Icon(icon, null, tint = Accent, modifier = Modifier.size(24.dp))
            Spacer(Modifier.width(13.dp))
            Column {
                Text(title, fontWeight = FontWeight.SemiBold, fontSize = 15.sp)
                Spacer(Modifier.height(5.dp))
                Text(detail, color = Muted, fontSize = 12.sp, lineHeight = 18.sp)
            }
        }
    }
}

@Composable
private fun ProfileScreen(
    loggedIn: Boolean, email: String, status: String, busy: Boolean, mode: String, password: String,
    code: String, backend: String, showServer: Boolean,
    onEmail: (String) -> Unit, onPassword: (String) -> Unit, onCode: (String) -> Unit,
    onBackend: (String) -> Unit, onMode: (String) -> Unit, onToggleServer: () -> Unit,
    onProfileSetup: () -> Unit, onLogout: () -> Unit, onSubmit: () -> Unit
) {
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(22.dp), verticalArrangement = Arrangement.spacedBy(13.dp)) {
        item { PageHeader("Your VOSI identity", "One account for your connected companion.") }
        item {
            Surface(color = Panel, shape = RoundedCornerShape(24.dp), border = androidx.compose.foundation.BorderStroke(1.dp, BorderGlow), modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Outlined.AccountCircle, null, tint = Accent, modifier = Modifier.size(30.dp))
                        Spacer(Modifier.width(10.dp))
                        Column {
                            Text(if (loggedIn) "Account connected" else "Connect your account", fontWeight = FontWeight.SemiBold)
                            Text(if (loggedIn) email else "Sign in or create your VOSI account", color = Muted, fontSize = 12.sp)
                        }
                    }
                    if (!loggedIn) {
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            listOf("Sign in", "Create account", "Verify email").forEach { choice ->
                                FilterChip(selected = mode == choice, onClick = { onMode(choice) }, label = { Text(choice, fontSize = 10.sp) })
                            }
                        }
                        OutlinedTextField(value = email, onValueChange = onEmail, label = { Text("Email address") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                        if (mode != "Verify email") {
                            var passText = password
                            OutlinedTextField(value = passText, onValueChange = onPassword, label = { Text("Password (10+ characters)") }, singleLine = true, visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth())
                        } else {
                            OutlinedTextField(value = code, onValueChange = onCode, label = { Text("6-digit email code") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                        }
                        Button(onClick = onSubmit, enabled = !busy, modifier = Modifier.fillMaxWidth().height(50.dp), shape = RoundedCornerShape(15.dp)) {
                            if (busy) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp) else Text(mode)
                        }
                    } else {
                        Text("Your account session is stored encrypted on this phone.", color = Muted, fontSize = 12.sp)
                        OutlinedButton(onClick = onLogout, modifier = Modifier.fillMaxWidth()) { Text("Sign out") }
                    }
                    Text(status, color = Muted, fontSize = 12.sp, lineHeight = 18.sp)
                }
            }
        }
        item {
            Surface(color = Panel, shape = RoundedCornerShape(20.dp), modifier = Modifier.fillMaxWidth().clickable(onClick = onProfileSetup)) {
                Row(Modifier.padding(17.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Outlined.Tune, null, tint = Accent)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text("Personal preferences", fontWeight = FontWeight.SemiBold)
                        Text("Name, language, country and shopping preferences", color = Muted, fontSize = 11.sp)
                    }
                    Icon(Icons.Outlined.ChevronRight, null, tint = Muted)
                }
            }
        }
        item {
            TextButton(onClick = onToggleServer) { Text(if (showServer) "Hide server settings" else "Advanced: server settings") }
            if (showServer) {
                OutlinedTextField(value = backend, onValueChange = onBackend, label = { Text("VOSI backend URL") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                Text("Use your deployed HTTPS API URL, or localhost/ADB reverse for development. Account registration requires backend SMTP and identity secrets to be configured.", color = Muted, fontSize = 11.sp)
            }
        }
        item { Text("VOSI never asks for merchant passwords, OTPs, UPI PINs or card security codes.", color = Muted, fontSize = 11.sp) }
    }
}

private fun identityRequest(base: String, path: String, method: String, token: String?, body: JSONObject): JSONObject {
    require(base.startsWith("https://") || base.startsWith("http://")) { "Enter a valid backend URL." }
    val connection = (URL(base + path).openConnection() as HttpURLConnection)
    try {
        connection.requestMethod = method
        connection.connectTimeout = 10000
        connection.readTimeout = 15000
        connection.setRequestProperty("Accept", "application/json")
        if (token != null) connection.setRequestProperty("Authorization", "Bearer $token")
        if (method != "GET") {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json")
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        }
        val code = connection.responseCode
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val raw = stream?.bufferedReader()?.use { it.readText() } ?: "{}"
        val result = JSONObject(raw)
        if (code !in 200..299) throw IllegalStateException(result.optString("detail", "VOSI request failed (HTTP $code)."))
        return result
    } finally { connection.disconnect() }
}

object AccountSessionStore {
    private const val Alias = "vosi_account_session_v1"
    private const val Prefs = "vosi_account_session_secure"
    fun save(token: String, email: String) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val encrypted = cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        VosiSessionContext.app?.getSharedPreferences(Prefs, 0)?.edit()
            ?.putString("iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            ?.putString("data", Base64.encodeToString(encrypted, Base64.NO_WRAP))
            ?.putString("email", email)?.apply()
    }
    fun load(): String? {
        return try {
            val prefs = VosiSessionContext.app?.getSharedPreferences(Prefs, 0) ?: return null
            val ivText = prefs.getString("iv", null) ?: return null
            val dataText = prefs.getString("data", null) ?: return null
            val iv = Base64.decode(ivText, Base64.NO_WRAP)
            val data = Base64.decode(dataText, Base64.NO_WRAP)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, iv))
            String(cipher.doFinal(data), Charsets.UTF_8)
        } catch (_: Exception) { null }
    }
    fun email(): String? = VosiSessionContext.app?.getSharedPreferences(Prefs, 0)?.getString("email", null)
    fun clear() { VosiSessionContext.app?.getSharedPreferences(Prefs, 0)?.edit()?.clear()?.apply() }
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(Alias, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder(Alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        return generator.generateKey()
    }
}

private object VosiSessionContext { var app: android.content.Context? = null }
