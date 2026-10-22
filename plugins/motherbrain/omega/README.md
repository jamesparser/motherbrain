# Motherbrain plugin for Omega (native)

Omega (SingularityNET, MeTTa/PeTTa) loads plugins listed in `config/plugins.yaml`.
This plugin gives every Omega agent the shared fleet brain:

| skill | does |
|---|---|
| `(mb-recall "task")` | memories + hard lessons from **every** agent; lessons first, "apply before planning" |
| `(mb-remember "fact")` | durable fact into shared long-term |
| `(mb-lesson "trigger" "rule")` | hard lesson for the whole fleet; rewrites the soul |
| `(mb-outcome "task" "ok\|fail")` | feeds the before/after ledger |

**Live soul, no reboot.** The soul (tone + hard lessons) is a prompt extension
(`motherbrain_soul`). A heartbeat listener checks the brain once a minute and swaps the
extension when the soul hash changes — i.e. another agent's lesson shows up in Omega's
prompt on the next turn without restarting Omega.

Tested in a throwaway Omega container (same image, mock channel + mock provider):
plugin loads, 4 skills registered, soul injected, heartbeat registered, agent joins the brain.
`ssh vps 'bash -s' < plugins/motherbrain/omega/test-plugin-in-throwaway-container.sh`

## Enable on the live Omega (compose)

1. Copy `plugin/` to `/opt/omega/plugins-motherbrain/` and write the token:
   `printf '%s' "$MB_API_KEY" > /opt/omega/plugins-motherbrain/.token && chmod 644 .../.token`
2. `docker exec omega cat /PeTTa/repos/Omega/config/plugins.yaml > /opt/omega/omega/plugins.yaml` and append
   ```yaml
   - name: motherbrain
     loader: metta
     location: "{REPO}/plugins/motherbrain"
   ```
3. In `compose.yaml` (service `omega`) add volumes
   `./plugins-motherbrain:/PeTTa/repos/Omega/plugins/motherbrain:ro` and
   `./omega/plugins.yaml:/PeTTa/repos/Omega/config/plugins.yaml:ro`, and append to `command`:
   `motherbrainEnabled=enabled`, `motherbrainURL=http://<vps-tailnet-ip>:8790`, `motherbrainAgent=omega`.
   (Command line, not env: Omega drops the container env when it switches user.)
4. `docker compose up -d omega`. Look for `Plugin motherbrain is loaded` in `docker logs omega`.

Rollback: remove the two volumes + three command args, `docker compose up -d omega`.
