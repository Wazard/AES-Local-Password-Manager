import secrets
import string

LOWERCASE = string.ascii_lowercase
UPPERCASE = string.ascii_uppercase
DIGITS = string.digits
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?"

# Pool used by the animated "decryption" effect in the UI.
SCRAMBLE_POOL = LOWERCASE + UPPERCASE + DIGITS + SYMBOLS


GROUP_SIZE = 6  # Apple-style: characters are shown in hyphen-separated groups.


def generate_secure_password(
    length: int = 18,
    use_upper: bool = True,
    use_digits: bool = True,
    use_symbols: bool = True,
    grouped: bool = True,
) -> str:
    """
    Generates a high-entropy password from a configurable character set.

    Lowercase letters are always included. Uppercase letters, digits, and
    symbols are optional. When a class is enabled it is guaranteed to appear
    at least once, so the result always satisfies the selected complexity.

    When ``grouped`` is True the characters are returned in Apple-style
    hyphen-separated blocks (e.g. ``aB3dfg-9hJkl2-...``).
    """
    charset = LOWERCASE
    required = [secrets.choice(LOWERCASE)]

    if use_upper:
        charset += UPPERCASE
        required.append(secrets.choice(UPPERCASE))
    if use_digits:
        charset += DIGITS
        required.append(secrets.choice(DIGITS))
    if use_symbols:
        charset += SYMBOLS
        required.append(secrets.choice(SYMBOLS))

    # Keep the length sane and never shorter than the guaranteed characters.
    length = max(length, len(required), 8)

    chars = required + [secrets.choice(charset) for _ in range(length - len(required))]

    # Cryptographically secure shuffle so required chars aren't front-loaded.
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]

    password = "".join(chars)

    if grouped:
        password = "-".join(
            password[i:i + GROUP_SIZE] for i in range(0, len(password), GROUP_SIZE)
        )

    return password
