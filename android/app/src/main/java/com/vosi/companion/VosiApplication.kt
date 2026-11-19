package com.vosi.companion

import android.app.Application

class VosiApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        VosiBackgroundTaskScheduler.ensureScheduled(this)
    }
}
