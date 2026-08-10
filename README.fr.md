# VoicePipe SSH

Streame le micro de votre machine locale vers la carte son virtuelle d'un
serveur distant (VPS) via SSH, avec une petite app tray Linux pour
allumer/eteindre les streams par host.

Cas d'usage typique : vous travaillez sur un VPS en SSH et vous voulez de
l'entree voix la-bas (speech-to-text, saisie vocale Claude Code, tout
programme qui enregistre depuis un micro). VoicePipe fait apparaitre
votre micro local sur le VPS comme un peripherique de capture ALSA
ordinaire.

English version: [README.md](README.md)

```
machine locale                     VPS
-----------------                  -------------------------------
micro -> arecord -- ssh (PCM brut) --> aplay -> loopback snd-aloop
                                                  ^
                                       n'importe quel enregistreur le lit
                                       comme un micro (plughw:Loopback,1,0)
```

Latence d'environ 150-200 ms de bout en bout avec les tampons par defaut.
PCM brut, sans compression : environ 96 ko/s en 48 kHz mono.

## Organisation du depot

- `client/` — machine locale : `voicepipe.sh` (moteur de streaming) et
  `voicetray.py` (app tray PyQt5 avec interrupteurs par host).
- `server/` — cote VPS : `setup-vps.sh` (installation idempotente du
  loopback).
- Chaque dossier contient un `CLAUDE.md` pour que Claude Code (ou tout
  agent) installe ce cote-la sans rien casser.

## Prerequis

Client (bureau Linux local) :

| Paquet (nom Debian)    | Role                                  |
|------------------------|---------------------------------------|
| `openssh-client`       | transport                             |
| `alsa-utils`           | capture `arecord` (ou `ffmpeg`)       |
| `python3`, `python3-pyqt5` | app tray                          |
| `sox` (optionnel)      | signal de test `--tone`               |

Serveur (VPS) :

| Paquet                 | Role                                  |
|------------------------|---------------------------------------|
| `alsa-utils`           | lecture `aplay` vers le loopback      |
| `snd-aloop` (module noyau) | carte son virtuelle               |

L'authentification SSH par cle est obligatoire (les scripts utilisent
`BatchMode=yes`, aucun mot de passe ne sera demande).

## Installation

Serveur, en root sur le VPS :

```
cd server
./setup-vps.sh --persist
```

Client :

```
cd client
./voicepipe.sh --check    # VPS_HOST=user@mon-vps ./voicepipe.sh --check
./install.sh              # lanceur de menu ; --autostart pour le demarrage
python3 voicetray.py
```

## L'app tray

L'app decouvre les hosts dans `~/.ssh/config` : chaque bloc `Host` qui
declare un `IdentityFile` recoit un interrupteur (les patterns a jokers
et `github.com` sont ignores ; ajoutez d'autres exclusions dans
`~/.config/voicepipe/ignore`, un host par ligne).

- Un interrupteur par host ; plusieurs streams peuvent tourner en meme
  temps.
- Un interrupteur maitre « Transmission » avec voyant vert/gris : le
  couper arrete tous les streams sans toucher aux interrupteurs par
  host ; le retablir relance les liaisons dont l'interrupteur est ON.
- Icone tray : verte quand la transmission est active, orange quand elle
  est coupee. Clic gauche : afficher/masquer la fenetre ; clic droit :
  les memes interrupteurs en menu.
- Un stream mort (reseau coupe, preflight rate) repasse son interrupteur
  a OFF et affiche l'erreur ; pas de reconnexion automatique, par choix.
- Logs par host dans `~/.cache/voicepipe/<host>.log`.

## Le moteur sans interface

`voicepipe.sh` fonctionne seul, configure par variables d'environnement
(`VPS_HOST`, `MIC`, `RATE`, `BUFFER_US`, `PERIOD_US`) :

```
VPS_HOST=user@mon-vps ./voicepipe.sh --check   # verifie les deux bouts
VPS_HOST=user@mon-vps ./voicepipe.sh           # streame jusqu'a Ctrl-C
VPS_HOST=user@mon-vps ./voicepipe.sh --tone    # ton de test 1 kHz
```

En cas de micro-coupures (xruns), remontez les tampons :
`BUFFER_US=200000 PERIOD_US=50000`.

## Paquet Debian

`./build-deb.sh` construit `voicepipe_<version>_all.deb` (cote client :
commande `voicetray`, entree de menu, icones ; la version vient de
`voicetray.py`). Installation :

```
sudo apt install ./voicepipe_*.deb
```

Un paquet pret a l'emploi est joint a chaque release GitHub.
Le `client/install.sh` reste l'alternative sans root.

## Versions

Source unique : `__version__` dans `client/voicetray.py` (affichee en
bas de la fenetre). Chaque release recoit un tag git correspondant
(`v1.0.0`, ...).

## Teste sur

- Client : Debian avec KDE Plasma.
- Serveur : VPS sous Debian.

Les autres distributions et bureaux Linux devraient fonctionner : le
client n'a besoin que de Python 3, PyQt5 et d'une zone de notification ;
le serveur uniquement de `snd-aloop` et `alsa-utils`.
