# 🛡️ Secure Vault

A lightweight, cross-platform password manager built with Python and CustomTkinter. Secure Vault features a high-performance AES-encrypted storage system and a unique "decryption-style" animated password generator.

## ✨ Features

* **AES Encryption**: All data is secured using industry-standard AES encryption before being saved to disk.
* **Multi-Language Support**: Fully localized in English, Italian, French and Danish.
* **Password Generator**: A safe password generator to fully secure your accounts.
* **Zero-Knowledge Architecture**: Your master password is never stored; data can only be decrypted locally on your machine.
* **Modern UI**: Built with a sleek, dark-themed interface designed for high scannability.

## 🚀 Installation & Usage

1.  **Download**: Grab the latest `gui_app.exe` from the [Releases](https://github.com/your-username/your-repo/releases) tab.
2.  **Run**: Double-click the executable. On first launch, it will prompt you to create a Master Password.
3.  **The Vault**: The app will create a file named `vault.pwmanager` in the same directory. **Do not delete this file**, as it contains all your encrypted accounts.

## 🛠️ Built With

* **Python**: Core logic and encryption.
* **CustomTkinter**: Modern GUI components.
* **Nuitka**: Compiled for performance and security.

## 📜 Credits & Attributions

### 🎨 Icon Attribution
The application icon used in this project was created by **Freepik** from [Flaticon](https://www.flaticon.com/).

### 🌍 Localization
Translations are managed via a dynamic `locales.json` system.
* **English**
* **Italian**
* **French**
* **Danish**

## ⚖️ License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
