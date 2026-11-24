import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

// One version number for every app: core/version.py.
val appVersion: String = Regex("^VERSION = \"(.*)\"", RegexOption.MULTILINE)
    .find(rootProject.file("../core/version.py").readText())?.groupValues?.get(1) ?: "0.0.0"

// The desktop's palette, bundled so the phone follows its colours (as on iOS).
abstract class CopyPalette : DefaultTask() {
    @get:InputFile abstract val palette: RegularFileProperty
    @get:OutputDirectory abstract val outputDir: DirectoryProperty

    @TaskAction
    fun copy() {
        palette.get().asFile.copyTo(outputDir.get().file("palette.json").asFile, overwrite = true)
    }
}

val copyPalette = tasks.register<CopyPalette>("copyPalette") {
    palette.set(rootProject.layout.projectDirectory.file("../UI/palette.json"))
}

// Release signing comes from the environment (CI secrets, see android/README.md).
// Without it the release APK is signed with the debug key, which installs fine
// but can't be updated by a build signed with a different key.
val keystore: String? = System.getenv("SV_KEYSTORE")?.takeIf { it.isNotBlank() }

android {
    namespace = "app.securevault.android"
    compileSdk = 35

    defaultConfig {
        applicationId = "app.securevault.android"
        minSdk = 26
        targetSdk = 35
        versionCode = System.getenv("VERSION_CODE")?.toIntOrNull() ?: 1
        versionName = appVersion
    }

    signingConfigs {
        if (keystore != null) {
            create("release") {
                storeFile = file(keystore)
                storePassword = System.getenv("SV_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("SV_KEY_ALIAS")
                keyPassword = System.getenv("SV_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName(if (keystore != null) "release" else "debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    testOptions {
        unitTests.all {
            // The vaults the desktop's own code wrote (ios/tools/make_fixtures.py),
            // shared with the iOS tests.
            it.systemProperty("sv.fixtures", rootProject.file("../ios/SecureVaultTests/Fixtures").absolutePath)
            // Where to leave files for the desktop-side checks (ios/tools/check_*.py).
            it.systemProperty("sv.export", System.getenv("SV_EXPORT_DIR") ?: "")
        }
    }
}

androidComponents {
    onVariants { variant ->
        variant.sources.assets?.addGeneratedSourceDirectory(copyPalette, CopyPalette::outputDir)
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(JvmTarget.JVM_17)
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.fragment:fragment-ktx:1.8.5")
    implementation("androidx.biometric:biometric:1.1.0")
    implementation("androidx.lifecycle:lifecycle-process:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    // Argon2id and PBKDF2 (the lightweight API only; no JCA provider is installed).
    implementation("org.bouncycastle:bcprov-jdk18on:1.78.1")

    testImplementation("junit:junit:4.13.2")
}
