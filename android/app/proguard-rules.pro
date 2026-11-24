# Only Bouncy Castle's lightweight Argon2 / PBKDF2 classes are used, directly
# (no reflection, no JCA provider). The rest of the jar refers to JDK classes
# Android doesn't have; R8 drops that code, so the references don't matter.
-dontwarn org.bouncycastle.**
