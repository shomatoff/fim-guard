# Security and privacy

## Data handling

FIM reads only folders explicitly selected by the user. It never modifies monitored files, sends files to a server, or stores file contents. SQLite stores selected root paths, relative file paths, SHA-256 digests, scan summaries and event timestamps. Logs and databases stay in the operating system's local application data directory unless a database path is explicitly supplied.

A symlinked root folder is rejected. Symlinked files and subfolders are skipped, as are nonregular objects such as named pipes. The application's SQLite database and its journal files are excluded if a user selects a folder containing them. The scanner opens files without following final symlinks where the operating system supports `O_NOFOLLOW`.

## Alert reliability

The scanner compares complete snapshots and checks file identity, size and modification time around hashing. If a file changes while being read, becomes inaccessible, a subtree cannot be visited, or the scan is interrupted, the scan is marked incomplete. It does not advance the baseline or issue change alerts from incomplete data. After a complete scan, the baseline advances atomically with the events in one SQLite transaction.

Watchdog notifications are debounced and supplemented by periodic full scans. A missed notification can delay an alert until the next reconciliation. Large trees require time to hash; the application does not claim tamper-proof evidence. A local attacker with access to the process or database can alter records. For stronger assurance, protect logs and store signed baselines independently.

## Sharing and repository hygiene

JSON and CSV reports contain paths and hashes, so review them before sharing. CSV text that could be interpreted as a spreadsheet formula is escaped on export. Do not commit real monitored content, the local database, logs, private reports, credentials or actual event logs. `.gitignore` excludes common generated data, but review `git status` before publishing. Report vulnerabilities privately to the repository owner.
