# Built-in music library licenses

`server/assets/music/library.json` is a JSON array. Each track entry needs:

`id`, `title`, `mood`, `duration_seconds`, `file` (relative to `server/assets/music/`),
`license_name`, `license_url`, `attribution`.

Before a track is added, put its full license text in this folder as `<id>.txt` and confirm the license
allows use inside users' videos (research R10, VERIFY 3). Until then the library stays empty and the UI
hides it.
