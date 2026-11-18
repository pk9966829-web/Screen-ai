package com.vosi.companion

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

internal data class VosiSettingOption(
    val title: String,
    val description: String,
    val status: String? = null,
    val action: String? = null
)

internal data class VosiSettingSection(
    val key: String,
    val title: String,
    val subtitle: String,
    val icon: ImageVector,
    val options: List<VosiSettingOption>
)

internal val VosiSettingSections = listOf(
    VosiSettingSection("general", "General", "Account, language, appearance and app behaviour", Icons.Outlined.Settings, listOf(
        VosiSettingOption("Account & profile", "Manage your VOSI identity and personal details", "Manage", "profile"),
        VosiSettingOption("Language", "The app currently follows your Android system language", "System", "language-info"),
        VosiSettingOption("Appearance", "VOSI keeps its signature dark visual style", "Dark", "appearance-info"),
        VosiSettingOption("Notifications", "Manage VOSI notification permission", "Manage", "notifications"),
        VosiSettingOption("Startup behaviour", "VOSI opens on the minimal Home screen", "Home")
    )),
    VosiSettingSection("ai", "AI & Intelligence", "Providers, models, backend and response behaviour", Icons.Outlined.Memory, listOf(
        VosiSettingOption("Backend connection", "Configure the VOSI API address and account connection", "Manage", "backend"),
        VosiSettingOption("Provider management", "Provider credentials and routing are controlled by the backend", "Backend", "backend"),
        VosiSettingOption("Default AI model", "The connected backend selects the active model", "Backend managed", "backend"),
        VosiSettingOption("Response style", "Response behaviour is currently controlled by the connected model", "Balanced", "model-info"),
        VosiSettingOption("Multi-agent orchestration", "Review task execution and agent activity", "View tasks", "tasks")
    )),
    VosiSettingSection("screen", "Screen Intelligence", "Observation, capture permissions and privacy", Icons.Outlined.Monitor, listOf(
        VosiSettingOption("Screen capture permission", "Android requires your approval each time a capture session starts", "System consent", "screen-info"),
        VosiSettingOption("Live observation", "The Android screen-observation service is not enabled in this build", "Not enabled", "screen-info"),
        VosiSettingOption("Sampling frequency", "Frame sampling will be configured by the observation service", "Not configured", "screen-info"),
        VosiSettingOption("Private content protection", "Screen capture must be started explicitly by you", "User controlled", "screen-info"),
        VosiSettingOption("Observation history", "No screen frames are stored by this settings screen", "No sessions")
    )),
    VosiSettingSection("voice", "Voice & Communication", "Speech input, voice output and microphone", Icons.Outlined.Mic, listOf(
        VosiSettingOption("Voice workspace", "Open VOSI's native voice and phone tools", "Open", "companion"),
        VosiSettingOption("Microphone permission", "Review microphone access granted to VOSI", "Manage", "app-settings"),
        VosiSettingOption("Speech output", "Android text-to-speech is available in the companion workspace", "Available", "companion"),
        VosiSettingOption("Spoken browser recommendations", "Configure spoken recommendations in the companion workspace", "Configure", "companion"),
        VosiSettingOption("Wake-word activation", "Always-on wake-word listening is not enabled in this build", "Not enabled")
    )),
    VosiSettingSection("device", "Device Control", "Pairing, connected devices and device permissions", Icons.Outlined.Devices, listOf(
        VosiSettingOption("Pair this phone", "Enter a secure one-time VOSI pairing code", "Open pairing", "companion"),
        VosiSettingOption("Connection status", "Check the paired device and backend heartbeat", "Check", "companion"),
        VosiSettingOption("Device commands", "Open the command workspace on this phone", "Open", "companion"),
        VosiSettingOption("Notification access", "Manage access to notification previews", "Manage", "notification-access"),
        VosiSettingOption("Connected devices", "Review phone, desktop and browser connection status", "View", "devices")
    )),
    VosiSettingSection("connectors", "Connectors & Integrations", "Gmail, Google, browser and third-party services", Icons.Outlined.Extension, listOf(
        VosiSettingOption("Gmail", "Email access requires an enabled VOSI OAuth connection", "Not connected", "connector-info"),
        VosiSettingOption("Google services", "Calendar, Drive and Contacts require OAuth authorization", "Not connected", "connector-info"),
        VosiSettingOption("Browser integration", "Browser context requires a paired VOSI browser companion", "Not connected", "connector-info"),
        VosiSettingOption("Chrome extension", "Pair the VOSI extension before using browser actions", "Not connected", "connector-info"),
        VosiSettingOption("Third-party apps", "External integrations require backend authorization", "Not connected", "connector-info")
    )),
    VosiSettingSection("agents", "Automation & Agents", "AI assistants, task execution and approvals", Icons.Outlined.SmartToy, listOf(
        VosiSettingOption("Chat assistant", "Open the shared VOSI conversation", "Open", "chat"),
        VosiSettingOption("Voice assistant", "Open the native voice workspace", "Open", "companion"),
        VosiSettingOption("Screen observer", "Android screen-observation service is not enabled yet", "Not enabled", "screen-info"),
        VosiSettingOption("Automation agent", "Review tasks and execution progress", "View tasks", "tasks"),
        VosiSettingOption("Task approvals", "Sensitive actions continue to require your explicit approval", "Required", "tasks")
    )),
    VosiSettingSection("security", "Security & Privacy", "Permissions, credentials and personal data", Icons.Outlined.Shield, listOf(
        VosiSettingOption("Device credentials", "Paired-device credentials are encrypted with Android Keystore", "Protected"),
        VosiSettingOption("App permissions", "Review microphone, notification and other app permissions", "Manage", "app-settings"),
        VosiSettingOption("Notification access", "Manage notification-listener permission", "Manage", "notification-access"),
        VosiSettingOption("Account security", "Review your VOSI account session", "Manage", "profile"),
        VosiSettingOption("Local notification previews", "Open the companion workspace to review or clear saved previews", "Open", "companion")
    )),
    VosiSettingSection("about", "About VOSI", "Version, system information and support", Icons.Outlined.Info, listOf(
        VosiSettingOption("Application version", "Installed VOSI Android application version", "0.2.0"),
        VosiSettingOption("Platform", "Native Android application built with Jetpack Compose", "Android"),
        VosiSettingOption("Build information", "Build and package details are available in Android app info", "View", "app-settings"),
        VosiSettingOption("Documentation", "VOSI documentation is not configured in this build", "Unavailable", "about-info"),
        VosiSettingOption("Support & feedback", "Support contact is not configured in this build", "Unavailable", "about-info")
    ))
)

@Composable
internal fun VosiSettingsDrawer(
    search: String,
    onSearch: (String) -> Unit,
    onSelect: (VosiSettingSection) -> Unit,
    onNavigate: (String) -> Unit,
    onClose: () -> Unit
) {
    Box(
        Modifier.fillMaxSize().background(Color(0x99000000)),
        contentAlignment = Alignment.CenterStart
    ) {
        Surface(
            modifier = Modifier.fillMaxHeight().widthIn(max = 340.dp).width(312.dp),
            color = Color(0xF20D0B13),
            shape = RoundedCornerShape(topEnd = 25.dp, bottomEnd = 25.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x55FF4CB8)),
            shadowElevation = 22.dp
        ) {
            Column(
                Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()
                    .padding(horizontal = 17.dp, vertical = 14.dp)
            ) {
                Row(
                    Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column {
                        Text("VOSI AI", color = Color.White, fontSize = 21.sp, fontWeight = FontWeight.ExtraBold, letterSpacing = 1.6.sp)
                        Text("NAVIGATION & SETTINGS", color = Color(0xFFFF70C5), fontSize = 9.sp, letterSpacing = 1.2.sp)
                    }
                    IconButton(onClick = onClose) {
                        Icon(Icons.Outlined.Close, "Close menu", tint = Color.White)
                    }
                }
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = search,
                    onValueChange = onSearch,
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    placeholder = { Text("Find a setting…", color = Color(0xFF91899A), fontSize = 13.sp) },
                    leadingIcon = { Icon(Icons.Outlined.Search, null, tint = Color(0xFFFF70C5)) },
                    shape = RoundedCornerShape(15.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Color(0xFFFF55B7),
                        unfocusedBorderColor = Color(0x443D3444),
                        focusedTextColor = Color.White,
                        unfocusedTextColor = Color.White,
                        cursorColor = Color(0xFFFF55B7)
                    )
                )
                Spacer(Modifier.height(14.dp))
                Text("QUICK ACCESS", color = Color(0xFF9A91A1), fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.1.sp)
                Spacer(Modifier.height(7.dp))
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                    DrawerQuickAction("Home", Icons.Outlined.Home, Modifier.weight(1f)) { onNavigate("home") }
                    DrawerQuickAction("Chat", Icons.Outlined.Forum, Modifier.weight(1f)) { onNavigate("chat") }
                    DrawerQuickAction("Tasks", Icons.Outlined.TaskAlt, Modifier.weight(1f)) { onNavigate("tasks") }
                    DrawerQuickAction("Devices", Icons.Outlined.Devices, Modifier.weight(1f)) { onNavigate("devices") }
                }
                Spacer(Modifier.height(16.dp))
                Text("SETTINGS", color = Color(0xFF9A91A1), fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.1.sp)
                Spacer(Modifier.height(7.dp))
                val filtered = VosiSettingSections.filter {
                    search.isBlank() || it.title.contains(search, true) || it.subtitle.contains(search, true) ||
                        it.options.any { option -> option.title.contains(search, true) || option.description.contains(search, true) }
                }
                LazyColumn(
                    modifier = Modifier.weight(1f).fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(7.dp),
                    contentPadding = PaddingValues(bottom = 12.dp)
                ) {
                    items(filtered, key = { it.key }) { section ->
                        Surface(
                            modifier = Modifier.fillMaxWidth().clickable { onSelect(section) },
                            color = Color(0x661C1722),
                            shape = RoundedCornerShape(15.dp),
                            border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x22FFFFFF))
                        ) {
                            Row(
                                Modifier.padding(horizontal = 12.dp, vertical = 12.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(section.icon, null, tint = Color(0xFFFF70C5), modifier = Modifier.size(21.dp))
                                Spacer(Modifier.width(11.dp))
                                Column(Modifier.weight(1f)) {
                                    Text(section.title, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                                    Text(section.subtitle, color = Color(0xFF9C94A5), fontSize = 10.sp, lineHeight = 14.sp, maxLines = 2)
                                }
                                Icon(Icons.Outlined.ChevronRight, null, tint = Color(0xFF817789), modifier = Modifier.size(19.dp))
                            }
                        }
                    }
                }
                Text("Sensitive actions still require your approval.", color = Color(0xFF9A91A1), fontSize = 10.sp)
            }
        }
    }
}

@Composable
private fun DrawerQuickAction(label: String, icon: ImageVector, modifier: Modifier, onClick: () -> Unit) {
    Surface(
        modifier = modifier.clickable(onClick = onClick),
        color = Color(0x661C1722),
        shape = RoundedCornerShape(12.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x22FFFFFF))
    ) {
        Column(
            Modifier.padding(vertical = 10.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Icon(icon, null, tint = Color(0xFFFF70C5), modifier = Modifier.size(18.dp))
            Text(label, color = Color(0xFFD9D2DE), fontSize = 10.sp)
        }
    }
}

@Composable
internal fun VosiSettingsDetailScreen(
    section: VosiSettingSection,
    onBack: () -> Unit,
    onAction: (String) -> Unit
) {
    Column(
        Modifier.fillMaxSize().background(Color(0xF20B0B0F))
            .statusBarsPadding().navigationBarsPadding()
    ) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 13.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.Outlined.ArrowBack, "Back to settings", tint = Color.White)
            }
            Column(Modifier.weight(1f)) {
                Text(section.title, color = Color.White, fontSize = 19.sp, fontWeight = FontWeight.Bold)
                Text(section.subtitle, color = Color(0xFF9A91A1), fontSize = 10.sp, maxLines = 1)
            }
            Icon(section.icon, null, tint = Color(0xFFFF70C5), modifier = Modifier.size(23.dp))
            Spacer(Modifier.width(8.dp))
        }
        HorizontalDivider(color = Color(0x22FFFFFF))
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(horizontal = 17.dp, vertical = 14.dp),
            verticalArrangement = Arrangement.spacedBy(9.dp)
        ) {
            item {
                Text("SETTINGS", color = Color(0xFFFF70C5), fontSize = 10.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.2.sp)
            }
            items(section.options, key = { it.title }) { option ->
                Surface(
                    modifier = Modifier.fillMaxWidth().then(
                        if (option.action != null) Modifier.clickable { onAction(option.action) } else Modifier
                    ),
                    color = Color(0xFF151219),
                    shape = RoundedCornerShape(17.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, Color(0x22FFFFFF))
                ) {
                    Row(
                        Modifier.padding(horizontal = 15.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(option.title, color = Color(0xFFF3EFF5), fontSize = 13.sp, fontWeight = FontWeight.Medium)
                            Spacer(Modifier.height(4.dp))
                            Text(option.description, color = Color(0xFF9B93A2), fontSize = 11.sp, lineHeight = 16.sp)
                        }
                        Spacer(Modifier.width(10.dp))
                        Column(horizontalAlignment = Alignment.End) {
                            if (!option.status.isNullOrBlank()) {
                                Text(option.status, color = if (option.status.contains("Not", true) || option.status.contains("Unavailable", true)) Color(0xFFE4A3B9) else Color(0xFFFF80C9), fontSize = 9.sp, fontWeight = FontWeight.SemiBold)
                            }
                            if (option.action != null) {
                                Icon(Icons.Outlined.ChevronRight, null, tint = Color(0xFF776E7E), modifier = Modifier.size(18.dp))
                            }
                        }
                    }
                }
            }
            item {
                Text(
                    "Options that need an Android permission or a backend integration will only become active after that capability is configured.",
                    color = Color(0xFF817989),
                    fontSize = 10.sp,
                    lineHeight = 15.sp,
                    modifier = Modifier.padding(top = 8.dp, bottom = 18.dp)
                )
            }
        }
    }
}
