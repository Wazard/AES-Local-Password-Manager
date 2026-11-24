package app.securevault.android.core

import java.security.SecureRandom

/** Ports of core/password_generator.py and core/password_strength.py. */
object PasswordGenerator {
    const val LOWERCASE = "abcdefghijklmnopqrstuvwxyz"
    const val UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    const val DIGITS = "0123456789"
    const val SYMBOLS = "!@#\$%^&*()-_=+[]{};:,.?"
    const val GROUP_SIZE = 6
    private val random = SecureRandom()

    /** Lowercase is always in; each enabled class appears at least once. */
    fun generate(
        length: Int = 18,
        upper: Boolean = true,
        digits: Boolean = true,
        symbols: Boolean = true,
        grouped: Boolean = true,
    ): String {
        var charset = LOWERCASE
        val chars = mutableListOf(LOWERCASE.pick())
        for ((on, set) in listOf(upper to UPPERCASE, digits to DIGITS, symbols to SYMBOLS)) {
            if (!on) continue
            charset += set
            chars.add(set.pick())
        }
        val target = maxOf(length, chars.size, 8)
        while (chars.size < target) chars.add(charset.pick())
        chars.shuffle(random)
        val password = chars.joinToString("")
        return if (grouped) password.chunked(GROUP_SIZE).joinToString("-") else password
    }

    private fun String.pick(): Char = this[random.nextInt(length)]
}

object PasswordStrength {
    val labels = listOf("Very weak", "Weak", "Fair", "Good", "Strong")

    class Result(val score: Int, val ok: Boolean)

    /** Score 0–4. `ok` is the minimum for a new master password
     *  (at least 8 characters and "fair"), same rule as the desktop. */
    fun evaluate(password: String): Result {
        val classes = listOf(
            password.any { it in 'a'..'z' },
            password.any { it in 'A'..'Z' },
            password.any { it in '0'..'9' },
            password.any { it !in 'a'..'z' && it !in 'A'..'Z' && it !in '0'..'9' },
        ).count { it }
        val n = password.codePointCount(0, password.length)
        var score = 0
        if (n >= 8) score++
        if (n >= 12) score++
        if (classes >= 2) score++
        if (classes >= 3 && n >= 10) score++
        score = minOf(score, 4)
        return Result(score, n >= 8 && score >= 2)
    }
}
