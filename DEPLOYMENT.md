# Deployment auf der Synology

Diese Anleitung beschreibt, wie die App auf dem NAS `ds218-dls` eingerichtet wird. Mit ihr lässt
sie sich neu aufsetzen oder auf ein anderes Synology-NAS umziehen. Die Entscheidungen dahinter
stehen in `Plan.md` (Schritt 8). Vorbild ist das Deployment von `purchase-prices` auf demselben NAS.

> **Stand 2026-11-21:** Die App ist nach dieser Anleitung eingerichtet und läuft. Die Vermerke
> „Erledigt“ bei den Schritten halten fest, was dabei geprüft wurde.

**Ergebnis:** `https://mitgliederdb.dorfladen-schlichten.de` → Reverse Proxy des DSM (HTTPS, Let's
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

`mitgliederdb.dorfladen-schlichten.de` wird ein **CNAME auf `work.dorfladen-schlichten.de`**, wie
`ek.` für `purchase-prices`. Die IP von `work.` hält die FritzBox per DynDNS aktuell.

1. Strato-Login → Domains → Domainverwaltung → **`dorfladen-schlichten.de`** (die Hauptdomain) →
   DNS-Verwaltung → CNAME-Record anlegen:
   - Präfix: `mitgliederdb`
   - Wert: `work.dorfladen-schlichten.de`
2. Prüfen, nach ein paar Minuten:

   ```sh
   dig +noall +answer mitgliederdb.dorfladen-schlichten.de A      # CNAME auf work. und dessen A-Record
   dig +noall +answer mitgliederdb.dorfladen-schlichten.de AAAA   # darf KEINE AAAA-Adresse liefern
   ```

   Ein AAAA-Eintrag (z. B. auf das Strato-Webhosting) würde Browser mit IPv6 woandershin schicken.

   **Erledigt 2026-11-21:** CNAME auf `work.`, A-Record 195.245.19.98, keine AAAA-Adresse.

## 3. Zertifikat im DSM

Systemsteuerung → Sicherheit → **Zertifikat** → Hinzufügen → „Neues Zertifikat hinzufügen“ →
„Zertifikat von Let's Encrypt abrufen“:

- Domainname: `mitgliederdb.dorfladen-schlichten.de`, dazu eine E-Mail-Adresse, alternativer Name leer
- „Als Standardzertifikat festlegen“: **aus**

Das DSM erneuert das Zertifikat selbst. Zugewiesen wird es in Schritt 9.

**Erledigt 2026-11-21:** Zertifikat `mitgliederdb.dorfladen-schlichten.de` von Let's Encrypt, nicht
Standard. Auf dem NAS prüfen (Ordnername je Zertifikat zufällig):

```sh
sudo sh -c 'for f in /usr/syno/etc/certificate/_archive/*/cert.pem; do openssl x509 -in $f -noout -subject -enddate; done'
```

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

**Erledigt 2026-11-21.** Vorher erbte der neue Ordner von der Freigabe auch `Aufsichtsrat` und die
leere Gruppe `group::` (alle), jeweils mit `level:2`. Danach stehen nur noch die drei Einträge mit
`level:0` da, genau wie bei `purchase-prices`. `data/` erbt sie (`level:1`):

```sh
sudo /usr/syno/bin/synoacltool -get $D/data     # drei Einträge mit level:1
```

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

**Erledigt 2026-11-21.** Prüfen, ohne das Secret anzuzeigen:

```sh
grep -v '^CM_SECRET_KEY=' $D/.env                                  # alle anderen Zeilen
grep -c '^CM_SECRET_KEY=[0-9a-f]\{64\}$' $D/.env                    # 1
sudo /usr/syno/bin/synoacltool -get $D/.env                          # drei Einträge mit level:1
```

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

**Erledigt 2026-11-21:** Der erste Bau dauerte gut 2 Minuten. Nach etwa 30 s meldete der
Container `healthy`, ohne Neustart. `/` und `/members/5` liefern die Vue-App, `/api/me` 401,
`/docs` ebenfalls die Vue-App (Doku aus). `purchase-prices` lief daneben unverändert weiter.

## 8. Reverse Proxy vertrauen

Anfragen des DSM-Proxys kommen vom **Gateway des Compose-Netzes**:

```sh
$DK network inspect coop-manager_default -f '{{range .IPAM.Config}}{{.Gateway}}{{end}}'   # z. B. 172.19.0.1
```

Diese Adresse in `$D/.env` bei `CM_TRUSTED_PROXIES=` eintragen, die ACL der Datei wiederherstellen
und den Container neu erzeugen:

```sh
sed -i 's/^CM_TRUSTED_PROXIES=.*/CM_TRUSTED_PROXIES=172.19.0.1/' $D/.env
sudo /usr/syno/bin/synoacltool -enforce-inherit $D/.env    # sed -i hat die ACL entfernt, siehe unten
sudo /usr/syno/bin/synoacltool -get $D/.env                # drei Einträge mit level:1
cd $D && $DK compose up -d --force-recreate
curl -s -D - -o /dev/null -H "X-Forwarded-Proto: https" -H "X-Forwarded-For: 203.0.113.5" \
    http://127.0.0.1:8001/ | grep -i strict-transport     # HSTS-Header = Proxy wird vertraut
$DK logs --tail 1 coop-manager-app-1                       # beginnt mit 203.0.113.5
```

> **Achtung bei `.env` und anderen Dateien im Projektordner:** `sed -i` (und manche Editoren)
> schreiben eine neue Datei und ersetzen die alte. Die neue Datei hat dann **keine ACL** mehr, sondern
> `rwxrwxrwx` ohne `+`, ist also für alle lesbar. Nach jeder solchen Änderung
> `synoacltool -enforce-inherit <datei>` ausführen und mit `ls -l` prüfen, dass das `+` wieder da ist.
>
> Wer eine Datei ändern will, ohne die ACL zu verlieren, schreibt in die bestehende Datei, z. B.
> `C=$(sed 's/alt/neu/' $D/.env) && printf '%s\n' "$C" > $D/.env`. `>` behält die Datei (gleiche
> Inode, `ls -i`) und damit ihre ACL.

**Erledigt 2026-11-21:** Gateway `172.19.0.1` (bei `purchase-prices` `172.18.0.1`). Vorher kein
HSTS-Header und im Log die Gateway-Adresse, nachher HSTS und `203.0.113.5` im Log.

## 9. Reverse Proxy im DSM

Systemsteuerung → **Anmeldeportal** → Erweitert → **Reverse Proxy** → Erstellen:

| Feld | Wert |
|---|---|
| Beschreibung | `coop-manager` |
| Quelle: Protokoll / Hostname / Port | `HTTPS` / `mitgliederdb.dorfladen-schlichten.de` / `443` |
| HSTS aktivieren | **aus** (die App setzt HSTS selbst) |
| Ziel: Protokoll / Hostname / Port | `HTTP` / `localhost` / `8001` |
| Benutzerdefinierte Kopfzeile | nichts. Das DSM schickt `X-Forwarded-For` und `X-Forwarded-Proto` von sich aus |

Danach Systemsteuerung → Sicherheit → Zertifikat → **Einstellungen**: beim Dienst
`mitgliederdb.dorfladen-schlichten.de` das gleichnamige Zertifikat auswählen.

**Erledigt 2026-11-21.** Die erzeugte nginx-Konfiguration lässt sich auf dem NAS prüfen
(`proxy_pass http://localhost:8001`, `X-Forwarded-For` und `X-Forwarded-Proto` gesetzt):

```sh
sudo awk '/mitgliederdb.dorfladen-schlichten.de/,/^}/' /etc/nginx/sites-enabled/server.ReverseProxy.conf
```

## 10. Von außen prüfen

Von einem Rechner außerhalb des Ladennetzes:

```sh
U=https://mitgliederdb.dorfladen-schlichten.de
echo | openssl s_client -connect mitgliederdb.dorfladen-schlichten.de:443 \
    -servername mitgliederdb.dorfladen-schlichten.de 2>/dev/null \
    | openssl x509 -noout -subject -enddate                          # CN=mitgliederdb.dorfladen-schlichten.de
curl -s -D - -o /dev/null $U/ | grep -i -E "^HTTP|strict"           # 200 und HSTS
curl -s -o /dev/null -w "%{http_code}\n" $U/api/me                  # 401, nicht angemeldet
curl -s -o /dev/null -w "%{http_code}\n" $U/docs                    # 200, aber die Vue-App, keine API-Doku
curl -s -o /dev/null -w "%{http_code}\n" $U/openapi.json            # 200, ebenfalls die Vue-App
```

Im Container-Log (`$DK logs --tail 5 coop-manager-app-1`) muss die öffentliche IP des prüfenden
Rechners stehen, nicht die Gateway-Adresse. Daran sieht man, dass die App dem Proxy vertraut und
damit erkennt, dass die Anfrage über HTTPS kam.

`http://mitgliederdb.dorfladen-schlichten.de` leitet nicht um, sondern zeigt die Standardseite der
Synology Web Station („Hello! Welcome to Synology Web Station!“), wie bei `ek.` auch. Die App ist
darüber nicht erreichbar. Den Link deshalb immer mit `https://` weitergeben.

**Erledigt 2026-11-21:** Zertifikat `CN=mitgliederdb.dorfladen-schlichten.de` von Let's Encrypt,
`HTTP/2 200` mit HSTS und CSP, `/members/5` 200, `/api/me` 401, `/docs` und `/openapi.json` die
Vue-App. Im Container-Log steht die öffentliche IP des prüfenden Rechners.

## 11. Ersteinrichtung

Im laufenden Container, auf dem NAS (`-it`, weil `create-admin` das Kennwort verdeckt abfragt):

```sh
$DK exec -it coop-manager-app-1 coop-manager create-admin
$DK exec coop-manager-app-1 coop-manager set-share-price 50
$DK exec coop-manager-app-1 coop-manager create-cooperative-account
$DK exec coop-manager-app-1 coop-manager show-settings
```

`create-admin` braucht ein echtes Terminal für die verdeckte Kennworteingabe. Vom eigenen Rechner
aus deshalb mit `ssh -t`:

```sh
ssh -t chef@ds218-dls-tail sudo /usr/local/bin/docker exec -it coop-manager-app-1 coop-manager create-admin
```

Danach im Browser als `admin` anmelden und unter **Benutzer** die Benutzer für Buchhaltung und
Vorstand anlegen.

**Erledigt 2026-11-21:** Admin angelegt (Matthias), Anteilspreis 50,00 €, Genossenschaftskonto 9999
„Unser Dorfladen Schlichten eG“. Im Event Store stehen danach genau drei Events
(`user.registered`, `settings.share-price-changed`, `account.opened`).

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

Die Kopie selbst prüfen (nur lesend):

```sh
sudo python3 -c "
import sqlite3; c=sqlite3.connect('file:$D/data/backup/eventstore.sqlite?mode=ro', uri=True)
print(c.execute('pragma journal_mode').fetchone(), c.execute('select count(*) from events').fetchone(),
      c.execute('pragma integrity_check').fetchone())"     # ('delete',) (Anzahl,) ('ok',)
```

Ob Hyper Backup den Ordner erfasst, zeigt seine Konfiguration (`backup_volumes`, `backup_filter`):

```sh
sudo grep -E "^(name|backup_volumes|backup_folders|backup_filter)=" /var/packages/HyperBackup/etc/synobackup.conf
```

**Erledigt 2026-11-21:** Aufgabe `coop-manager Sicherung` (root, täglich 20:00, E-Mail an
`webmaster@` nur bei Fehler) einmal von Hand ausgeführt. Die Kopie liegt in `data/backup/`, eine
Datei im Modus `delete`, Integritätsprüfung `ok`, mit der eingeschränkten ACL (`level:3`). Hyper
Backup („Synology C2“) sichert `/volume1`, ausgenommen ist nur `/photo/`; der Projektordner ist also
dabei. Die Aufgabe liegt auf dem NAS in `/usr/syno/etc/synoschedule.d/root/14.task`.

### Wiederherstellen

1. In Hyper Backup die Datei `IT-Systeme/Docker/coop-manager/data/backup/eventstore.sqlite`
   aus der gewünschten Version wiederherstellen, am besten zuerst in einen Testordner.
2. Container stoppen: `cd $D && $DK compose stop`
3. Die Datei als `$D/data/eventstore.sqlite` einsetzen, `$D/data/eventstore.sqlite-*` und
   `$D/data/projections.sqlite*` löschen.
4. Starten: `$DK compose start`. Die App baut die Projektionen neu auf. Die Login-Sperren gehen
   dabei verloren, das ist unkritisch.

## 13. Migration der Altdaten

Einmalig: Übernahme aus der Access-Datenbank des Altsystems (Schritt 7 im Plan). Die Migration
läuft **im laufenden Container** mit `coop-manager migrate`; sie schreibt in einer Transaktion und
bringt die Projektionen selbst auf den neuesten Stand. Kein Stopp, kein Kopieren der Datenbank.

Vorbereitung auf dem eigenen Rechner (`mdbtools`, siehe Logbuch): CSV-Export nach
`Altdaten/csv/` und die Einzelfälle in `Altdaten/migration.toml` (beides nicht im Repository).

```sh
./deploy.sh                                               # Stand mit dem Befehl migrate ausrollen
tar -C Altdaten -c csv/mitglieder.csv csv/mitglieder_hist.csv csv/buchungen.csv migration.toml \
    | ssh chef@ds218-dls-tail "mkdir -p $D/data/import && tar -C $D/data/import -x --no-same-owner"
ls -l $D/data/import $D/data/import/csv                   # auf dem NAS: überall „+“ (ACL geerbt)
$DK exec coop-manager-app-1 coop-manager migrate /data/import/csv /data/import/migration.toml --dry-run
$DK exec coop-manager-app-1 coop-manager migrate /data/import/csv /data/import/migration.toml
rm -rf $D/data/import                                     # echte Daten nicht liegen lassen
```

`migrate` bricht ab, wenn es schon Mitglieder gibt oder das Genossenschaftskonto fehlt, und vor dem
Speichern, wenn Plan, Aufbau oder Abgleich der Salden etwas melden.

**Erledigt 2026-11-21:** Probelauf und echter Lauf mit denselben Zahlen wie lokal (7d): 287 Personen
(249 Mitglieder, 11 abgelehnt, 27 ausgeschieden), 288 Buchungen, 1.120 Anteile, 56.000 €;
1.911 Events mit Akteur `migration`. Danach `healthy`, Saldenliste abgestimmt (Konto 9999
−56.000 €), 5 Konten mit nicht gebuchtem Ausscheiden (2015, 2016, 2017, 2021, 2023), die die
Buchhaltung unter „Jahresende“ bucht (am selben Tag erledigt, siehe Logbuch). Eine Sicherung vorher war nicht nötig, weil in der
Produktion noch nichts Wichtiges stand. `data/import` ist gelöscht.

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
| `.env` zeigt in `ls -l` kein `+`, `synoacltool -get` meldet „It's Linux mode“ | Datei mit `sed -i` oder einem Editor ersetzt, die ACL ist dabei verloren gegangen; die Datei ist für alle lesbar | `sudo /usr/syno/bin/synoacltool -enforce-inherit $D/.env` |
| Kein HSTS-Header, im Log steht die Gateway-Adresse | `CM_TRUSTED_PROXIES` passt nicht zum Gateway | Schritt 8 wiederholen |
| `sudo: docker: command not found` | `sudo` sucht nicht in `/usr/local/bin` | Vollen Pfad `/usr/local/bin/docker` nehmen |
| `Bind for 127.0.0.1:8001 failed: port is already allocated` | Ein anderer Container belegt den Port | Freien Port in `CM_PORT` und im Reverse Proxy eintragen |
