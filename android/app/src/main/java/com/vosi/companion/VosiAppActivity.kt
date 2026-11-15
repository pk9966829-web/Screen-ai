package com.vosi.companion

import android.content.Intent
import android.os.Bundle
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

private val Ink = Color(0xFF080A12)
private val Panel = Color(0xFF141827)
private val Soft = Color(0xFF20263A)
private val Accent = Color(0xFFB69CFF)
private val GlowBlue = Color(0xFF62D9F5)
private val Muted = Color(0xFF9BA5BC)
private val BorderGlow = Color(0x334E5E9B)

class VosiAppActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        VosiSessionContext.app = applicationContext
        window.statusBarColor = android.graphics.Color.rgb(8, 10, 18)
        window.navigationBarColor = android.graphics.Color.rgb(8, 10, 18)
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
    var navigationOpen by remember { mutableStateOf(false) }
    var chatDraft by remember { mutableStateOf("") }

    Box(Modifier.fillMaxSize()) {
        VosiAmbientBackground()
        Scaffold(
            containerColor = Color.Transparent,
            bottomBar = {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    androidx.compose.animation.AnimatedVisibility(
                        visible = navigationOpen,
                        enter = androidx.compose.animation.expandVertically() + androidx.compose.animation.fadeIn(),
                        exit = androidx.compose.animation.shrinkVertically() + androidx.compose.animation.fadeOut()
                    ) {
                        NavigationBar(
                            containerColor = Color(0xE6081425),
                            contentColor = Color.White,
                            tonalElevation = 0.dp
                        ) {
                            VosiTab.entries.forEach { item ->
                                val selected = tab == item
                                NavigationBarItem(
                                    selected = selected,
                                    onClick = { tab = item; navigationOpen = false },
                                    icon = {
                                        when (item) {
                                            VosiTab.HOME -> Icon(Icons.Outlined.Home, null)
                                            VosiTab.CHAT -> Icon(Icons.Outlined.Forum, null)
                                            VosiTab.TASKS -> Icon(Icons.Outlined.TaskAlt, null)
                                            VosiTab.DEVICES -> Icon(Icons.Outlined.Devices, null)
                                            VosiTab.PROFILE -> Icon(Icons.Outlined.Person, null)
                                        }
                                    },
                                    label = { Text(item.label, fontSize = 10.sp) },
                                    colors = NavigationBarItemDefaults.colors(
                                        selectedIconColor = GlowBlue, selectedTextColor = Color.White,
                                        indicatorColor = Color(0x3338BDF8),
                                        unselectedIconColor = Muted, unselectedTextColor = Muted
                                    )
                                )
                            }
                        }
                    }
                    Surface(
                        color = Color(0xE6081425),
                        modifier = Modifier.fillMaxWidth(),
                        shadowElevation = 8.dp
                    ) {
                        Row(
                            Modifier.fillMaxWidth().height(42.dp),
                            horizontalArrangement = Arrangement.Center,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            IconButton(onClick = { navigationOpen = !navigationOpen }) {
                                Icon(
                                    if (navigationOpen) Icons.Outlined.KeyboardArrowDown else Icons.Outlined.KeyboardArrowUp,
                                    contentDescription = if (navigationOpen) "Hide navigation" else "Show navigation",
                                    tint = Accent,
                                    modifier = Modifier.size(30.dp)
                                )
                            }
                        }
                    }
                }
            }
        ) { padding ->
            Box(Modifier.fillMaxSize().padding(padding)) {
                when (tab) {
                    VosiTab.HOME -> HomeScreen(
                        onChat = { tab = VosiTab.CHAT },
                        onSearch = { query -> chatDraft = query; tab = VosiTab.CHAT },
                        onTasks = { tab = VosiTab.TASKS },
                        onDevices = { tab = VosiTab.DEVICES },
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

        androidx.compose.animation.AnimatedVisibility(
            visible = settingsOpen,
            modifier = Modifier.align(Alignment.CenterStart),
            enter = androidx.compose.animation.slideInHorizontally(initialOffsetX = { -it }) + androidx.compose.animation.fadeIn(),
            exit = androidx.compose.animation.slideOutHorizontally(targetOffsetX = { -it }) + androidx.compose.animation.fadeOut()
        ) {
            Surface(
                modifier = Modifier.fillMaxHeight().width(286.dp),
                color = Color(0xF0081425),
                shape = RoundedCornerShape(topEnd = 26.dp, bottomEnd = 26.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x5538BDF8)),
                shadowElevation = 20.dp
            ) {
                Column(
                    Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(20.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                        Column {
                            Text("VOSI", color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.ExtraBold, letterSpacing = 2.sp)
                            Text("SETTINGS & SHORTCUTS", color = GlowBlue, fontSize = 9.sp, letterSpacing = 1.5.sp)
                        }
                        IconButton(onClick = { settingsOpen = false }) {
                            Icon(Icons.Outlined.ArrowBack, "Close settings", tint = Accent)
                        }
                    }
                    HorizontalDivider(color = Color(0x334E7498))
                    DrawerEntry("Account & profile", Icons.Outlined.Person) { tab = VosiTab.PROFILE; settingsOpen = false }
                    DrawerEntry("Server connection", Icons.Outlined.Cloud) { tab = VosiTab.PROFILE; showServerSettings = true; settingsOpen = false }
                    DrawerEntry("Connected devices", Icons.Outlined.Devices) { tab = VosiTab.DEVICES; settingsOpen = false }
                    DrawerEntry("Tasks & approvals", Icons.Outlined.TaskAlt) { tab = VosiTab.TASKS; settingsOpen = false }
                    Spacer(Modifier.weight(1f))
                    Text("Your control comes first. Sensitive actions still require your approval.", color = Muted, fontSize = 11.sp, lineHeight = 16.sp)
                }
            }
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
    val drift = androidx.compose.animation.core.rememberInfiniteTransition(label = "dashboard-ambient")
    val ambient by drift.animateFloat(
        initialValue = -1f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(9000), repeatMode = RepeatMode.Reverse),
        label = "ambient-drift"
    )
    val haze by drift.animateFloat(
        initialValue = 0.55f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(6000), repeatMode = RepeatMode.Reverse),
        label = "haze-shift"
    )
    Box(
        Modifier.fillMaxSize().background(
            Brush.verticalGradient(
                listOf(Color(0xFF08284A), Color(0xFF041B33), Color(0xFF021225), Color(0xFF010814))
            )
        )
    ) {
        Box(
            Modifier.align(Alignment.TopStart).offset(x = (-115).dp, y = (-105).dp)
                .size(390.dp).graphicsLayer {
                    translationX = ambient * 42.dp.toPx()
                    translationY = ambient * 30.dp.toPx()
                    alpha = 0.55f + ((ambient + 1f) * 0.12f)
                }
                .background(Brush.radialGradient(listOf(Color(0x5538BDF8), Color(0x2238BDF8), Color.Transparent)))
        )
        Box(
            Modifier.align(Alignment.TopEnd).offset(x = 145.dp, y = 80.dp)
                .size(360.dp).graphicsLayer {
                    translationX = -ambient * 48.dp.toPx()
                    translationY = ambient * 54.dp.toPx()
                    alpha = 0.42f + ((ambient + 1f) * 0.18f)
                }
                .background(Brush.radialGradient(listOf(Color(0x554F8EF7), Color(0x223B82F6), Color.Transparent)))
        )
        Box(
            Modifier.align(Alignment.BottomCenter).offset(y = 130.dp)
                .size(420.dp).graphicsLayer {
                    translationX = ambient * 38.dp.toPx()
                    translationY = -ambient * 48.dp.toPx()
                    alpha = 0.3f + ((ambient + 1f) * 0.16f)
                }
                .background(Brush.radialGradient(listOf(Color(0x4438BDF8), Color.Transparent)))
        )
        Box(
            Modifier.fillMaxSize().graphicsLayer {
                alpha = haze
                translationX = ambient * 8.dp.toPx()
                translationY = -ambient * 5.dp.toPx()
            }.background(
                Brush.verticalGradient(
                    0f to Color(0x11111D32),
                    0.48f to Color.Transparent,
                    1f to Color(0x66000510)
                )
            )
        )
    }
}

@Composable
private fun HomeScreen(
    onChat: () -> Unit,
    onSearch: (String) -> Unit,
    onTasks: () -> Unit,
    onDevices: () -> Unit,
    onTalk: () -> Unit,
    onOpenSettings: () -> Unit
) {
    var query by remember { mutableStateOf("") }
    var connectorsOpen by remember { mutableStateOf(false) }
    Column(
        Modifier.fillMaxSize().statusBarsPadding().padding(horizontal = 22.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = onOpenSettings) {
                Icon(Icons.Outlined.Menu, "Open settings", tint = Color.White, modifier = Modifier.size(27.dp))
            }
            Surface(
                color = Color(0x331B3952),
                shape = RoundedCornerShape(50),
                border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x5538BDF8))
            ) {
                Row(Modifier.padding(horizontal = 12.dp, vertical = 7.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(7.dp).clip(CircleShape).background(Color(0xFF68E5C2)))
                    Spacer(Modifier.width(7.dp))
                    Text("READY", color = Color(0xFFD2F8EC), fontSize = 9.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
                }
            }
        }
        Spacer(Modifier.height(26.dp))
        Text("Hi, I'm VOSI.", color = Color.White, fontSize = 34.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(10.dp))
        Text("What would you like to make happen?", color = Color(0xFFB9C8DC), fontSize = 14.sp)
        Spacer(Modifier.height(30.dp))
        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = Color(0xCC07182B),
            shape = RoundedCornerShape(24.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x7738BDF8)),
            shadowElevation = 14.dp
        ) {
            Row(
                Modifier.padding(start = 16.dp, end = 8.dp, top = 8.dp, bottom = 8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(Icons.Outlined.Search, null, tint = GlowBlue, modifier = Modifier.size(22.dp))
                Spacer(Modifier.width(10.dp))
                androidx.compose.foundation.text.BasicTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    textStyle = androidx.compose.ui.text.TextStyle(color = Color.White, fontSize = 14.sp),
                    cursorBrush = androidx.compose.ui.graphics.SolidColor(GlowBlue),
                    decorationBox = { inner ->
                        Box {
                            if (query.isBlank()) Text("Ask VOSI anything…", color = Color(0xFF879BB4), fontSize = 14.sp)
                            inner()
                        }
                    },
                    keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(imeAction = androidx.compose.ui.text.input.ImeAction.Search),
                    keyboardActions = androidx.compose.foundation.text.KeyboardActions(onSearch = { if (query.isNotBlank()) onSearch(query.trim()) })
                )
                IconButton(onClick = { connectorsOpen = true }) {
                    Icon(Icons.Outlined.Extension, "Open connectors", tint = Accent, modifier = Modifier.size(23.dp))
                }
                IconButton(onClick = { if (query.isNotBlank()) onSearch(query.trim()) }) {
                    Icon(Icons.Outlined.ArrowForward, "Send to VOSI", tint = GlowBlue)
                }
            }
        }
        Spacer(Modifier.height(14.dp))
        Text("VOICE  •  CHAT  •  TASKS  •  CONNECTED DEVICES", color = Color(0xFF8DA8C4), fontSize = 9.sp, letterSpacing = 1.6.sp)
        Spacer(Modifier.height(22.dp))
        TextButton(onClick = onTalk) {
            Icon(Icons.Outlined.GraphicEq, null, tint = Accent)
            Spacer(Modifier.width(8.dp))
            Text("Start a voice conversation", color = Accent, fontWeight = FontWeight.SemiBold)
        }
        Spacer(Modifier.height(12.dp))
        TextButton(onClick = onDevices) {
            Icon(Icons.Outlined.Devices, null, tint = GlowBlue)
            Spacer(Modifier.width(8.dp))
            Text("Connect your devices", color = Color(0xFFB8DDF2))
        }
    }

    if (connectorsOpen) {
        AlertDialog(
            onDismissRequest = { connectorsOpen = false },
            containerColor = Color(0xFF0A1B2D),
            title = { Text("VOSI connectors", color = Color.White) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Connect services and devices to extend what VOSI can do.", color = Muted, fontSize = 12.sp)
                    Text("Browser and desktop connections are managed from Connected devices. Account-based connectors will appear here when enabled for your VOSI account.", color = Color(0xFFB8C8DA), fontSize = 12.sp)
                }
            },
            confirmButton = {
                TextButton(onClick = { connectorsOpen = false; onDevices() }) {
                    Text("Connected devices", color = GlowBlue)
                }
            },
            dismissButton = {
                TextButton(onClick = { connectorsOpen = false }) { Text("Close", color = Accent) }
            }
        )
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
