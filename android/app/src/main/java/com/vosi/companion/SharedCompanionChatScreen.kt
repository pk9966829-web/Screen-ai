package com.vosi.companion

import android.content.Context
import android.os.Handler
import android.os.Looper
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

private val ChatInk = Color(0xFF0B0B0F)
private val ChatPanel = Color(0xB9151119)
private val ChatAccent = Color(0xFFFF70C5)
private val ChatMuted = Color(0xFF9BA5BC)

private data class CompanionChatMessage(val text: String, val fromUser: Boolean)

@Composable
fun SharedCompanionChatScreen(initialDraft: String = "") {
    val context = LocalContext.current
    var messages by remember {
        mutableStateOf(
            listOf(CompanionChatMessage("Hi, I'm VOSI. Your conversations can continue across your paired devices.", false))
        )
    }
    var draft by remember { mutableStateOf(initialDraft) }
    var busy by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf("Connecting to your paired VOSI phone…") }
    val listState = rememberLazyListState()

    LaunchedEffect(Unit) {
        val credential = DeviceCredentialStore.load(context)
        val accountToken = AccountSessionStore.load()
        if (credential == null) {
            status = "Pair this phone with VOSI in the device workspace to start shared chat."
        } else if (accountToken.isNullOrBlank()) {
            status = "Sign in to your VOSI account in Profile to use private shared chat."
        } else {
            status = "Loading your private shared conversation…"
            thread {
                try {
                    val history = companionChatRequest(
                        credential.getString("backend_url"),
                        "/companion/chat/history?limit=50",
                        "GET",
                        credential.getString("device_token"),
                        accountToken = accountToken
                    )
                    val restored = mutableListOf<CompanionChatMessage>()
                    val interactions = history.optJSONArray("interactions")
                    if (interactions != null) {
                        for (index in 0 until interactions.length()) {
                            val turn = interactions.optJSONObject(index) ?: continue
                            val question = turn.optString("question").trim()
                            val answer = turn.optString("answer").trim()
                            if (question.isNotEmpty()) restored.add(CompanionChatMessage(question, true))
                            if (answer.isNotEmpty()) restored.add(CompanionChatMessage(answer, false))
                        }
                    }
                    Handler(Looper.getMainLooper()).post {
                        if (restored.isNotEmpty()) messages = restored
                        status = "Shared chat is ready."
                    }
                } catch (error: Exception) {
                    Handler(Looper.getMainLooper()).post {
                        status = error.message ?: "Couldn't load shared chat. Check the phone pairing and backend."
                    }
                }
            }
        }
    }

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) listState.animateScrollToItem(messages.lastIndex)
    }

    Column(
        Modifier.fillMaxSize().background(Color.Transparent).padding(horizontal = 18.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(
                Modifier.size(48.dp).background(
                    Brush.radialGradient(listOf(Color(0xFFFF3FB4), Color(0xFF8A35B8), ChatPanel)),
                    RoundedCornerShape(50)
                ),
                contentAlignment = Alignment.Center
            ) {
                Icon(Icons.Outlined.AllInclusive, null, tint = Color.White, modifier = Modifier.size(29.dp))
            }
            Column {
                Text("VOSI", fontSize = 20.sp, fontWeight = FontWeight.Bold, color = Color.White, letterSpacing = 1.sp)
                Text("Your conversation", color = ChatMuted, fontSize = 11.sp)
            }
        }

        LazyColumn(
            modifier = Modifier.weight(1f).fillMaxWidth(),
            state = listState,
            contentPadding = PaddingValues(vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            items(messages) { message ->
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = if (message.fromUser) Arrangement.End else Arrangement.Start
                ) {
                    Surface(
                        color = if (message.fromUser) Color(0xB95D2B57) else ChatPanel,
                        shape = RoundedCornerShape(
                            topStart = 18.dp, topEnd = 18.dp,
                            bottomStart = if (message.fromUser) 18.dp else 5.dp,
                            bottomEnd = if (message.fromUser) 5.dp else 18.dp
                        ),
                        modifier = Modifier.widthIn(max = 320.dp)
                    ) {
                        Text(
                            message.text,
                            color = Color.White,
                            fontSize = 14.sp,
                            lineHeight = 20.sp,
                            modifier = Modifier.padding(horizontal = 15.dp, vertical = 12.dp)
                        )
                    }
                }
            }
        }

        Text(status, color = ChatMuted, fontSize = 11.sp)

        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.Bottom,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedTextField(
                value = draft,
                onValueChange = { draft = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text("Message VOSI…") },
                enabled = !busy,
                maxLines = 4,
                shape = RoundedCornerShape(20.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = ChatAccent,
                    unfocusedBorderColor = Color(0xFF303A54),
                    focusedTextColor = Color.White,
                    unfocusedTextColor = Color.White,
                    cursorColor = ChatAccent,
                    focusedPlaceholderColor = ChatMuted,
                    unfocusedPlaceholderColor = ChatMuted
                )
            )
            FilledIconButton(
                onClick = {
                    val message = draft.trim()
                    if (message.isEmpty() || busy) return@FilledIconButton
                    val credential = DeviceCredentialStore.load(context)
                    val accountToken = AccountSessionStore.load()
                    if (credential == null) {
                        status = "Pair this phone with VOSI before sending a message."
                        return@FilledIconButton
                    }
                    if (accountToken.isNullOrBlank()) {
                        status = "Sign in to your VOSI account in Profile before sending a private message."
                        return@FilledIconButton
                    }
                    messages = messages + CompanionChatMessage(message, true)
                    draft = ""
                    busy = true
                    status = "VOSI is thinking…"
                    thread {
                        try {
                            val result = companionChatRequest(
                                credential.getString("backend_url"),
                                "/companion/chat",
                                "POST",
                                credential.getString("device_token"),
                                JSONObject().put("message", message),
                                accountToken
                            )
                            val answer = result.optString("response").trim()
                            if (!result.optBoolean("success") || answer.isEmpty()) {
                                throw IllegalStateException(answer.ifEmpty { "VOSI couldn't prepare a response. Please try again." })
                            }
                            Handler(Looper.getMainLooper()).post {
                                messages = messages + CompanionChatMessage(answer, false)
                                status = "Shared chat is ready."
                                busy = false
                            }
                        } catch (error: Exception) {
                            Handler(Looper.getMainLooper()).post {
                                status = error.message ?: "Message failed. Check your connection and try again."
                                busy = false
                            }
                        }
                    }
                },
                enabled = !busy && draft.isNotBlank(),
                modifier = Modifier.size(52.dp),
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = ChatAccent,
                    contentColor = ChatInk
                )
            ) {
                if (busy) {
                    CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                } else {
                    Icon(Icons.Outlined.Send, contentDescription = "Send message")
                }
            }
        }
    }
}

private fun companionChatRequest(
    baseUrl: String,
    path: String,
    method: String,
    token: String,
    body: JSONObject? = null,
    accountToken: String
): JSONObject {
    require(baseUrl.startsWith("https://") || baseUrl.startsWith("http://")) {
        "Your paired VOSI backend URL is invalid. Re-pair this phone if needed."
    }
    val connection = URL(baseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection
    try {
        connection.requestMethod = method
        connection.connectTimeout = 10000
        connection.readTimeout = 45000
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("Authorization", "Bearer $token")
        connection.setRequestProperty("X-VOSI-Account-Token", accountToken)
        if (body != null) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        }
        val code = connection.responseCode
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val raw = stream?.bufferedReader()?.use { it.readText() } ?: "{}"
        val response = JSONObject(raw)
        if (code !in 200..299) {
            throw IllegalStateException(
                response.optString("detail", "VOSI chat request failed (HTTP $code).")
            )
        }
        return response
    } finally {
        connection.disconnect()
    }
}
