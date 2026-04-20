# Deployment

## Source of Truth

Der Quellstand liegt unter `/home/alex/kids_controller`.

Der Produktivstand unter `/opt/kids_controller` ist ein Deployment-Ziel und
wird nur aus dem Quellstand aktualisiert. Direkte Hotfixes in `/opt` sollten
vermieden werden.

## Runtime-Konfiguration

- Produktive Umgebungsvariablen: `/etc/kids_controller/.env`
- Systemd-Unit: `/etc/systemd/system/kids-controller.service`
- Home-Assistant-Konfiguration: `/opt/docker/homeassistant/config`
- Versionierte systemd-Vorlage im Repo: `/home/alex/kids_controller/deploy/systemd/kids-controller.service`

Die Repo-Quelle enthält absichtlich nur `.env.example`, keine produktiven
Secrets.

## Erstinstallation

1. Quellstand nach `/opt/kids_controller` kopieren oder direkt deployen.
2. Produktive Umgebungsdatei anlegen:
   `sudo install -d -m 0755 /etc/kids_controller`
   `sudo cp /home/alex/kids_controller/.env.example /etc/kids_controller/.env`
3. Secrets und produktive Werte in `/etc/kids_controller/.env` setzen.
4. Systemd-Unit installieren:
   `sudo cp /home/alex/kids_controller/deploy/systemd/kids-controller.service /etc/systemd/system/kids-controller.service`
   `sudo systemctl daemon-reload`
   `sudo systemctl enable kids-controller.service`
5. Erstes Deploy ausführen:
   `sudo bash /home/alex/kids_controller/scripts/deploy.sh`

## Arbeitsablauf

1. Änderungen in `/home/alex/kids_controller` machen.
2. Tests lokal ausführen:
   `make test`
3. Drift prüfen:
   `make drift`
4. Deploy ausrollen:
   `sudo bash /home/alex/kids_controller/scripts/deploy.sh`
5. Live prüfen:
   `bash /home/alex/kids_controller/scripts/verify_live.sh`

## Verhalten des Deploy-Skripts

- synchronisiert den Quellstand nach `/opt/kids_controller`
- erstellt bei Bedarf `/opt/kids_controller/.venv`
- installiert das Projekt per `pip install -e /opt/kids_controller`
- startet danach den systemd-Dienst `kids-controller` neu

## Home Assistant

Nach Änderungen an `/opt/docker/homeassistant/config/scripts.yaml` oder
`rest_commands.yaml` müssen die Skripte bzw. Rest-Commands in Home Assistant
neu geladen werden.

## Backup

Vor größeren Änderungen liegt ein Vollbackup unter:

`/home/alex/kids_controller_professionalize_backup_20260420_071720`
