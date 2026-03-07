# Outlook integration — dev vs target checklist

Information needed to make the status engine’s Outlook integration work on your **target machine** (Windows 10) when developed on **Windows 11** with Outlook desktop. Covers COM-based polling and targeting specific folders (including shared inboxes).

---

## 1. Environment

| Item | Dev (your machine) | Target machine | Notes |
|------|--------------------|----------------|-------|
| OS | Windows 11 | Windows 10 | COM and Outlook object model are the same; Outlook build may differ. |
| Outlook | Desktop (Click-to-Run or MSI) | _____________ | Version (e.g. 2309, 2401) — note for compatibility. |
| .NET / Python | _____________ | _____________ | Status engine runtime (Python + pywin32, or C# with COM interop). |

**Outlook must be running** for COM to work. The process that runs the status engine (scheduled task, service, or manual) must run in a context where `Outlook.Application` can attach to the **same** Outlook instance the user sees. That usually means:

- **Run Only When User Is Logged On** — task runs in the logged-in user session; Outlook is often already running. Easiest.
- **Run Whether User Is Logged On** — runs as SYSTEM or a different account; Outlook is typically **not** running for that user, so COM will not see the mailbox. Avoid for COM-based polling unless you start Outlook in that session (not typical).

So on the target machine, plan for: user logged in, Outlook running, status engine (or scheduled task) running as that user.

---

## 2. Which folders to poll

The status engine will need to know **which folder(s)** to count unread / oldest-unread in. Options:

| Source | Description | COM notes |
|--------|-------------|-----------|
| **Default Inbox** | Primary account’s Inbox | `Namespace.GetDefaultFolder(olFolderInbox)` — simple. |
| **Named folder under default store** | e.g. "Support", "Alerts" under same mailbox | Walk folders from default Inbox parent or by name. |
| **Shared mailbox — Inbox** | Another mailbox added to the profile (e.g. shared inbox) | Appears as a separate store or under "Shared With Me" / additional mailbox root. Access via store by name or by walking `Namespace.Folders`. |
| **Shared mailbox — subfolder** | e.g. shared mailbox’s "Inbox\Alerts" | Same store as above, then walk to the subfolder by name or path. |

**What to record for the target:**

- **Profile name** (if multiple): _____________  
  COM uses the default profile unless you specify. If the target machine has only one Outlook profile, you can ignore this.
- **Folder to poll:**  
  - [ ] Default Inbox only  
  - [ ] Other folder(s) in primary mailbox: name/path _____________  
  - [ ] Shared mailbox: name or email _____________  
  - [ ] Shared mailbox subfolder: path _____________  

**How shared mailboxes appear in Outlook:**

- **Auto-mapped (recommended):** Admin adds the shared mailbox to the user; it shows under "Shared With Me" or as an extra root in the folder list. COM sees it as an extra `Store` or folder under `Namespace.Folders`.
- **Manual add:** User added the shared mailbox as a separate account or open another mailbox; again it appears as another store/folder tree.
- On the target machine, open Outlook and note the **exact name** of the store/folder as shown in the tree (e.g. "Support (shared)" or the mailbox display name). The status engine will resolve the folder by that name or by walking the folder tree.

---

## 3. COM folder resolution (reference)

Rough mapping for implementation:

- **Default Inbox:**  
  `Namespace.GetDefaultFolder(olFolderInbox)` → always the default account’s Inbox.
- **Store by name:**  
  Iterate `Namespace.Folders` (or `Stores`) and match `Store.DisplayName` (or similar) to the configured name.
- **Shared mailbox root / Inbox:**  
  Find the store for that mailbox, then get its Inbox: e.g. `store.GetDefaultFolder(olFolderInbox)`.
- **Subfolder by path:**  
  e.g. "Inbox\Alerts" → start from Inbox, then `Folders("Alerts")` (or walk by name). Folder names are localized in some Outlook versions; prefer English if both dev and target use it.

**Important:** Folder display names can differ between Windows 10 and 11 if Outlook language or version differs. Prefer **folder entry ID** (if you persist and reuse it) for a stable handle, or a configurable display name that you set per machine.

---

## 4. Config / code implications

The status engine (or its config) will need at least:

| Config key | Purpose | Example |
|------------|---------|--------|
| **Folder source** | Which mailbox/folder to poll | `"default_inbox"` or `"store_name"` + optional `"folder_path"` (e.g. `"Inbox\\Alerts"`) |
| **Store name** | For shared mailbox: display name of the store as shown in Outlook | `"Support (shared)"` — must match target. |
| **Profile name** | Only if target has multiple profiles and you need a non-default one | Usually omit. |

Suggest: a small config section, e.g. in `config/channels.json` or a dedicated `outlook.json`, with something like:

```json
"outlook": {
  "folderSource": "default_inbox",
  "storeDisplayName": null,
  "folderPath": null
}
```

For shared inbox: set `folderSource` to `"shared_store"` (or similar), set `storeDisplayName` to the exact store name from the target, and optionally `folderPath` (e.g. `"Inbox"` or `"Inbox\\Alerts"`).

---

## 5. Target-machine checklist

Before deploying the status engine on Windows 10:

- [ ] **Outlook desktop** installed and updated (same major version as dev if possible).
- [ ] **Single profile** in use, or profile name noted and config set if needed.
- [ ] **Shared mailbox** (if used) is visible in Outlook folder list; note the **exact display name** of the store/mailbox.
- [ ] **Folder to poll** identified: default Inbox, or store + folder path.
- [ ] **Scheduled task** (or run method) set to “Run Only When User Is Logged On” so Outlook is running in the same session.
- [ ] **Run once manually** as the target user: status engine can open Outlook via COM and open the target folder; log folder name and unread count for verification.

---

## 6. Windows 10 vs 11 differences (practical)

- **COM:** Same Outlook object model; no OS-specific COM changes for this use case.
- **Outlook version:** Click-to-Run can differ by machine. If dev is 2309 and target is 2206, folder names and minor APIs are usually the same; test opening the desired folder and reading unread count on the target.
- **Permissions:** Ensure the target user has **read** access to the shared mailbox and the specific folder. Auto-mapping usually grants this.

---

## 7. Summary table — fill in for target

| Field | Value (target machine) |
|-------|------------------------|
| OS | Windows 10 |
| Outlook version | _____________ |
| Profile name (if not default) | _____________ |
| Folder to poll | Default Inbox / Other: _____________ |
| Shared mailbox store name (if any) | _____________ |
| Subfolder path (if any) | _____________ |
| How status engine will run | Scheduled task, user logged on |

Once this is filled in, implementation can use it to open the correct folder and apply the same “oldest unread” logic on both dev and target.
