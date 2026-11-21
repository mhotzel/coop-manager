# Deployment auf der Synology

Diese Anleitung beschreibt, wie die App auf dem NAS `ds218-dls` eingerichtet wird. Mit ihr lässt
sie sich neu aufsetzen oder auf ein anderes Synology-NAS umziehen. Die Entscheidungen dahinter
stehen in `Plan.md` (Schritt 8). Vorbild ist das Deployment von `purchase-prices` auf demselben NAS.

> **Stand 2026-11-21:** Die Anleitung ist geschrieben, die Einrichtung auf dem NAS steht noch aus.
> Beim Durchgehen werden echte Werte und neue Fehlerbilder hier nachgetragen.

**Ergebnis:** `https://mitglieder.dorfladen-schlichten.de` → Reverse Proxy des DSM (HTTPS, Let's
Encrypt) → `http://localhost:8001` → Container `coop-manager-app-1` (uvicorn) → `data/` auf dem NAS.

| | |
|---|---|
| NAS | Synology DS218, DSM 7.4, ARM64, Container Manager (Docker 24, Compose v2.20) |
| Zugang | `ssh chef@ds218-dls-tail` (über Tailscale, auch von außerhalb des Ladennetzes), `sudo` ohne Kennwort |
| Projektordner | `/volume1/IT-Systeme/Docker/coop-manager` (darin `.env` und `data/`) |
| Container läuft als | `chef`, uid 1029, gid 100 (`users`) |
| Port | `127.0.0.1:8001` (8000 belegt `purchase-prices`) |
| Docker | `sudo /usr/local/bin/docker` (`chef` ist nicht in der Gruppe `docker`, und `sudo` sucht nicht in `/usr/local/bin`) |

Alle Befehle mit `ssh` oder `./deploy.sh` laufen auf dem eigenen Rechner im Projektordner, alle
anderen auf dem NAS. Auf dem NAS hilft:

```sh
D=/volume1/IT-Systeme/Docker/coop-manager
DK="sudo /usr/local/bin/docker"
```

## 1. Voraussetzungen prüfen

Für `purchase-prices` ist das alles schon eingerichtet, hier nur zur Kontrolle:

- Im DSM ist **Container Manager** installiert (Paketzentrum).
- SSH ist aktiviert (Systemsteuerung → Terminal & SNMP), und der Login als `chef` klappt ohne Kennwort.
- Im Router (FritzBox) sind die Ports **80 und 443** zum NAS weitergeleitet. Port 80 braucht
  Let's Encrypt für die Prüfung des Namens.
- uid und gid von `chef`, sie kommen in die `.env`:

  ```sh
  ssh chef@ds218-dls-tail id       # uid=1029(chef) gid=100(users) …
  ```

## 2. DNS bei Strato

`mitglieder.dorfladen-schlichten.de` wird ein **CNAME auf `work.dorfladen-schlichten.de`**, wie
`ek.` für `purchase-prices`. Die IP von `work.` hält die FritzBox per DynDNS aktuell.

1. Strato-Login → Domains → Domainverwaltung → **`dorfladen-schlichten.de`** (die Hauptdomain) →
   DNS-Verwaltung → CNAME-Record anlegen:
   - Präfix: `mitglieder`
   - Wert: `work.dorfladen-schlichten.de`
2. Prüfen, nach ein paar Minuten:

   ```sh
   dig +noall +answer mitglieder.dorfladen-schlichten.de A      # CNAME auf work. und dessen A-Record
   dig +noall +answer mitglieder.dorfladen-schlichten.de AAAA   # darf KEINE AAAA-Adresse liefern
   ```

   Ein AAAA-Eintrag (z. B. auf das Strato-Webhosting) würde Browser mit IPv6 woandershin schicken.

## 3. Zertifikat im DSM

Systemsteuerung → Sicherheit → **Zertifikat** → Hinzufügen → „Neues Zertifikat hinzufügen“ →
„Zertifikat von Let's Encrypt abrufen“:

- Domainname: `mitglieder.dorfladen-schlichten.de`, dazu eine E-Mail-Adresse, alternativer Name leer
- „Als Standardzertifikat festlegen“: **aus**

Das DSM erneuert das Zertifikat selbst. Zugewiesen wird es in Schritt 9.

## 4. Projektordner mit eingeschränkten Rechten

Die Freigabe `IT-Systeme` vererbt Vollzugriff auch an die Gruppen `Aufsichtsrat` und `users`.
`.env` enthält das Secret und `data/` die **Mitgliederdaten** und Kennwort-Hashes, deshalb bekommt
der Ordner eigene Rechte: nur `chef`, `administrators` und `IT-Admin`. Das muss **vor** dem Anlegen
von `.env` und `data/` passieren, denn die Dateien erben die Rechte des Ordners.

```sh
mkdir -p $D
A="sudo /usr/syno/bin/synoacltool"
$A -add $D user:chef:allow:rwxpdDaARWc--:fd--
$A -add $D group:administrators:allow:rwxpdDaARWc--:fd--
$A -add $D group:IT-Admin:allow:rwxpdDaARWc--:fd--
$A -del-archive $D is_inherit         # Vererbung von der Freigabe abschalten
$A -get $D                            # darf nur noch die drei Einträge mit level:0 zeigen
mkdir -p $D/data
```

`ls -l` zeigt weiterhin `rwxrwxrwx+`. Maßgeblich ist die ACL (`+`), nicht die Unix-Rechte.

## 5. `.env` auf dem NAS

Das Secret wird direkt auf dem NAS erzeugt und verlässt es nicht. `CM_TRUSTED_PROXIES` bleibt
vorerst leer, die Adresse ergibt sich erst in Schritt 8.

```sh
test ! -e $D/.env && cat > $D/.env <<EOF
CM_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
CM_LOG_LEVEL=INFO
# Gateway des Compose-Netzes: von dort kommen die Anfragen des DSM-Reverse-Proxys
CM_TRUSTED_PROXIES=
CM_SESSION_TIMEOUT=1800
CM_SESSION_COOKIE_SECURE=true
CM_LOGIN_MAX_ATTEMPTS=3
CM_LOGIN_LOCKOUT_SECONDS=900
CM_COOPERATIVE_ACCOUNT_NAME=Unser Dorfladen Schlichten eG
CM_API_DOCS=false
CM_BIND_ADDRESS=127.0.0.1
CM_PORT=8001
CM_UID=1029
CM_GID=100
EOF
```

- `CM_DATA_DIR` und `CM_FRONTEND_DIR` fehlen mit Absicht, `compose.yaml` setzt sie fest.
- `CM_BIND_ADDRESS` muss `127.0.0.1` bleiben: Docker umgeht die Firewall des DSM, mit `0.0.0.0`
  wäre die App ohne HTTPS im ganzen Netz erreichbar.
- `CM_API_DOCS=false`: Im Betrieb gibt es keine API-Dokumentation unter `/docs`.

## 6. Daten

Die App startet **leer**. Die Altdaten aus Access kommen mit der Migration (Schritt 7 im Plan).
Entwicklungsdaten vom eigenen Rechner gehören nicht auf das NAS.

Wer später einen vorhandenen Stand übertragen will (Umzug, Wiederherstellung), nimmt dafür eine
Sicherung (`coop-manager backup`, siehe Schritt 12), nie die laufende Datenbank:

```sh
tar -C <ordner mit der Sicherung> -c eventstore.sqlite \
    | ssh chef@ds218-dls-tail "tar -C /volume1/IT-Systeme/Docker/coop-manager/data -x"
```

`projections.sqlite` ist nicht nötig, die App baut die Projektionen beim Start neu auf.

## 7. Bauen und starten

```sh
./deploy.sh
```

`deploy.sh` überträgt `Dockerfile`, `compose.yaml`, `.dockerignore`, aus `backend/` die Dateien
`pyproject.toml`, `uv.lock` und `src/` und aus `frontend/` die Quellen (ohne `node_modules` und
`dist`) per `tar` in den Projektordner. Dort baut es das Image und startet mit
`docker compose up -d --build`. `.env` und `data/` bleiben unberührt.

Gebaut wird **auf dem NAS**: Es ist ARM64, der eigene Rechner meist x86. Beim ersten Mal dauert
das einige Minuten, weil auch `npm ci` und der Vite-Build dort laufen.

Prüfen, auf dem NAS:

```sh
$DK inspect -f '{{.State.Health.Status}}' coop-manager-app-1    # nach ~30 s: healthy
$DK logs --tail 20 coop-manager-app-1                            # keine Fehler
curl -s http://127.0.0.1:8001/healthz                            # {"status":"ok"}
```

## 8. Reverse Proxy vertrauen

Anfragen des DSM-Proxys kommen vom **Gateway des Compose-Netzes**:

```sh
$DK network inspect coop-manager_default -f '{{range .IPAM.Config}}{{.Gateway}}{{end}}'   # z. B. 172.19.0.1
```

Diese Adresse in `$D/.env` bei `CM_TRUSTED_PROXIES=` eintragen und den Container neu erzeugen:

```sh
cd $D && $DK compose up -d --force-recreate
curl -s -D - -o /dev/null -H "X-Forwarded-Proto: https" -H "X-Forwarded-For: 203.0.113.5" \
    http://127.0.0.1:8001/ | grep -i strict-transport     # HSTS-Header = Proxy wird vertraut
$DK logs --tail 1 coop-manager-app-1                       # beginnt mit 203.0.113.5
```

## 9. Reverse Proxy im DSM

Systemsteuerung → **Anmeldeportal** → Erweitert → **Reverse Proxy** → Erstellen:

| Feld | Wert |
|---|---|
| Beschreibung | `coop-manager` |
| Quelle: Protokoll / Hostname / Port | `HTTPS` / `mitglieder.dorfladen-schlichten.de` / `443` |
| HSTS aktivieren | **aus** (die App setzt HSTS selbst) |
| Ziel: Protokoll / Hostname / Port | `HTTP` / `localhost` / `8001` |
| Benutzerdefinierte Kopfzeile | nichts. Das DSM schickt `X-Forwarded-For` und `X-Forwarded-Proto` von sich aus |

Danach Systemsteuerung → Sicherheit → Zertifikat → **Einstellungen**: beim Dienst
`mitglieder.dorfladen-schlichten.de` das gleichnamige Zertifikat auswählen.

Die erzeugte nginx-Konfiguration lässt sich auf dem NAS prüfen:

```sh
sudo awk '/mitglieder.dorfladen-schlichten.de/,/^}/' /etc/nginx/sites-enabled/server.ReverseProxy.conf
```

## 10. Von außen prüfen

Von einem Rechner außerhalb des Ladennetzes:

```sh
U=https://mitglieder.dorfladen-schlichten.de
echo | openssl s_client -connect mitglieder.dorfladen-schlichten.de:443 \
    -servername mitglieder.dorfladen-schlichten.de 2>/dev/null \
    | openssl x509 -noout -subject -enddate                          # CN=mitglieder.dorfladen-schlichten.de
curl -s -D - -o /dev/null $U/ | grep -i -E "^HTTP|strict"           # 200 und HSTS
curl -s -o /dev/null -w "%{http_code}\n" $U/api/me                  # 401, nicht angemeldet
curl -s -o /dev/null -w "%{http_code}\n" $U/docs                    # 200, aber die Vue-App, keine API-Doku
curl -s -o /dev/null -w "%{http_code}\n" $U/openapi.json            # 200, ebenfalls die Vue-App
```

Im Container-Log (`$DK logs --tail 5 coop-manager-app-1`) muss die öffentliche IP des prüfenden
Rechners stehen, nicht die Gateway-Adresse. Daran sieht man, dass die App dem Proxy vertraut und
damit erkennt, dass die Anfrage über HTTPS kam.

`http://mitglieder.dorfladen-schlichten.de` liefert 404 und leitet nicht um. Den Link deshalb
immer mit `https://` weitergeben.

## 11. Ersteinrichtung

Im laufenden Container, auf dem NAS (`-it`, weil `create-admin` das Kennwort verdeckt abfragt):

```sh
$DK exec -it coop-manager-app-1 coop-manager create-admin
$DK exec coop-manager-app-1 coop-manager set-share-price 50
$DK exec coop-manager-app-1 coop-manager create-cooperative-account
$DK exec coop-manager-app-1 coop-manager show-settings
```

Danach im Browser als `admin` anmelden und unter **Benutzer** die Benutzer für Buchhaltung und
Vorstand anlegen.

## 12. Datensicherung

Hyper Backup sichert täglich um 20:30 das ganze `/volume1` nach Synology C2, also auch den
Projektordner. SQLite-Dateien im laufenden Betrieb zu kopieren ist aber nicht sicher. Deshalb
schreibt `coop-manager backup` vorher eine stimmige Kopie nach `data/backup/eventstore.sqlite`.

Systemsteuerung → **Aufgabenplaner** → Erstellen → Geplante Aufgabe → Benutzerdefiniertes Script:

| Feld | Wert |
|---|---|
| Aufgabe | `coop-manager Sicherung` |
| Benutzer | `root` |
| Zeitplan | täglich, **20:00** (vor Hyper Backup) |
| Benachrichtigung | per E-Mail, nur wenn das Script abnormal beendet wird |
| Script | `/usr/local/bin/docker exec coop-manager-app-1 coop-manager backup` |

Einmal mit „Ausführen“ starten und prüfen:

```sh
ls -l --time-style=full-iso $D/data/backup/        # Zeitstempel von eben
```

Ob Hyper Backup den Ordner erfasst, zeigt seine Konfiguration (`backup_volumes`, `backup_filter`):

```sh
sudo grep -E "^(name|backup_volumes|backup_folders|backup_filter)=" /var/packages/HyperBackup/etc/synobackup.conf
```

### Wiederherstellen

1. In Hyper Backup die Datei `IT-Systeme/Docker/coop-manager/data/backup/eventstore.sqlite`
   aus der gewünschten Version wiederherstellen, am besten zuerst in einen Testordner.
2. Container stoppen: `cd $D && $DK compose stop`
3. Die Datei als `$D/data/eventstore.sqlite` einsetzen, `$D/data/eventstore.sqlite-*` und
   `$D/data/projections.sqlite*` löschen.
4. Starten: `$DK compose start`. Die App baut die Projektionen neu auf. Die Login-Sperren gehen
   dabei verloren, das ist unkritisch.

## Updates und Rückfall

```sh
./deploy.sh                                  # aktuellen Stand ausrollen
git checkout <commit> && ./deploy.sh         # älteren Stand ausrollen, danach: git checkout main
```

`deploy.sh` überträgt das Arbeitsverzeichnis, also auch nicht committete Änderungen. Deshalb
vorher committen. Nach einem `docker compose down` (nicht bei `deploy.sh`) kann das Compose-Netz
ein anderes Subnetz bekommen. Dann das Gateway wie in Schritt 8 prüfen und `CM_TRUSTED_PROXIES`
anpassen.

## Fehlerbilder

Übernommen aus `purchase-prices`, soweit sie hier ebenso auftreten können:

| Symptom | Ursache | Abhilfe |
|---|---|---|
| `rsync`: „Permission denied, please try again“ | Die Synology erlaubt rsync über SSH nur mit aktiviertem rsync-Dienst | `deploy.sh` nimmt `tar`, für eigene Kopien ebenfalls `tar … \| ssh …` |
| Container `unhealthy`, `ModuleNotFoundError` oder `Permission denied` beim Start | Aus einer Freigabe mit ACL kommt der Code als `0700 root` ins Image, der Container-Benutzer kann ihn nicht lesen | `COPY --chmod=755` im Dockerfile (ist drin) |
| Container kann nicht in `/data` schreiben | `CM_UID`/`CM_GID` passen nicht zum Besitzer von `data/` | Werte aus `id` in die `.env` |
| Anmeldung klappt, aber die nächste Anfrage meldet „nicht angemeldet“ | Seite über `http://` aufgerufen, der Browser schickt das `Secure`-Cookie nicht mit | Über `https://` aufrufen. Nur ohne HTTPS (LAN-Test) `CM_SESSION_COOKIE_SECURE=false` |
| Kein HSTS-Header, im Log steht die Gateway-Adresse | `CM_TRUSTED_PROXIES` passt nicht zum Gateway | Schritt 8 wiederholen |
| `sudo: docker: command not found` | `sudo` sucht nicht in `/usr/local/bin` | Vollen Pfad `/usr/local/bin/docker` nehmen |
| `Bind for 127.0.0.1:8001 failed: port is already allocated` | Ein anderer Container belegt den Port | Freien Port in `CM_PORT` und im Reverse Proxy eintragen |
