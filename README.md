# metrorower

[![CI](https://github.com/mgurg/metrorower_strava_connector/actions/workflows/ci.yml/badge.svg)](https://github.com/mgurg/metrorower_strava_connector/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Eksport przejazdów rowerem miejskim **Metrorower** (Nextbike) do plików
**GPX**, gotowych do wgrania do Stravy, Garmin Connect czy Komoot.

Narzędzie pobiera szczegóły przejazdów z konta Nextbike, czyści ślad GPS
(przycina go do stacji wypożyczenia i zwrotu) i zapisuje jeden plik GPX na
przejazd.

```text
$ uv run metrorower
[360039555] zapisano gpx/20260909_metrorower_360039555.gpx (5.06 km, 458 punktów; dane z API)
[359818673] odrzucony: 0.62 km (< 1 km; dane z cache)
[358585546] pomijam: GPX już istnieje

Podsumowanie: pobrano=1, cache=1, utworzono_GPX=1, już_istniało=1, poniżej_limitu=1, błędy=0
```

## Funkcje

- **Ślad przycięty do stacji.** Na początku przejazdu GPS często nie ma
  jeszcze pozycji, a po zwrocie roweru zbiera punkty przy stacji. Ślad
  zaczyna się od punktu najbliższego stacji startowej (w pierwszych 120 s)
  i kończy na punkcie najbliższym stacji zwrotu (w ostatnich 120 s).
- **Dokładne punkty stacji.** Na początek i koniec śladu dopisywane są
  współrzędne stacji z czasem wypożyczenia i zwrotu. Stacja jest
  rozpoznawana po numerze z API, a gdy go brak, wybierana jest najbliższa
  stacja w promieniu 300 m.
- **Cache odpowiedzi.** Pełna odpowiedź API trafia do `data/<ID>.json`
  i przy kolejnym uruchomieniu API nie jest odpytywane ponownie.
- **Bez duplikatów.** Przejazdy, dla których plik GPX już istnieje, są
  pomijane.
- **Filtr krótkich przejazdów.** Przejazdy krótsze niż 1 km zostają
  w cache'u, ale nie są eksportowane.
- **Bezpieczny zapis.** Pliki są zapisywane atomowo, więc przerwanie
  programu nie zostawia uszkodzonego GPX ani JSON-a.

## Wymagania

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- konto Nextbike

## Instalacja

```bash
git clone https://github.com/mgurg/metrorower_strava_connector.git
cd metrorower_strava_connector
uv sync
```

## Przygotowanie

### `cookie.txt`

1. Zaloguj się na [account.nextbike.pl](https://account.nextbike.pl).
2. Otwórz narzędzia deweloperskie przeglądarki (F12) → *Application* /
   *Storage* → *Cookies*.
3. Skopiuj wartość cookie `nextbike-react` do pliku `cookie.txt`.

Plik może zawierać samą wartość (zaczynającą się od `Fe26.2`) albo całą
parę:

```text
nextbike-react=Fe26.2*...
```

### `ids.txt`

Identyfikatory przejazdów, po jednym w wierszu. Opcjonalny nagłówek `ID`,
puste wiersze i powtórzenia są ignorowane:

```text
ID
360039555
359818673
```

> [!IMPORTANT]
> `cookie.txt`, `ids.txt`, `data/` i `gpx/` zawierają dane prywatne
> (sesję i historię lokalizacji) i są ignorowane przez Git.

## Użycie

```bash
uv run metrorower
```

| Opcja | Domyślnie | Opis |
|---|---|---|
| `--ids` | `ids.txt` | plik z ID przejazdów |
| `--cookie` | `cookie.txt` | plik z cookie Nextbike |
| `--data-dir` | `data` | katalog odpowiedzi API (cache) |
| `--gpx-dir` | `gpx` | katalog wynikowych plików GPX |

Pliki GPX mają nazwy `YYYYMMDD_metrorower_<ID>.gpx`, gdzie data to lokalna
data rozpoczęcia przejazdu (`Europe/Warsaw`).

Kod wyjścia: `0` — wszystko w porządku, `1` — część przejazdów się nie
udała, `2` — błędne pliki wejściowe.

> [!TIP]
> Błąd `HTTP 401` oznacza, że sesja wygasła. Zaloguj się ponownie
> i skopiuj nowe cookie.

## Rozwój

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

Te same kroki uruchamia [CI](.github/workflows/ci.yml) przy każdym pushu
i pull requeście.

### Struktura kodu

| Moduł | Odpowiedzialność |
|---|---|
| `cli.py` | argumenty, raportowanie postępu i podsumowanie |
| `export.py` | przebieg eksportu i wynik dla każdego przejazdu |
| `rentals.py` | repozytorium przejazdów z cache'em odpowiedzi |
| `nextbike.py` | klient API Nextbike i parsowanie odpowiedzi |
| `models.py` | model domenowy (`Rental`, `Place`, `TrackPoint`) |
| `errors.py` | hierarchia wyjątków |
| `geo.py` | współrzędne i odległości |
| `stations.py` | stacje i wyszukiwanie najbliższej |
| `track.py` | przycinanie śladu i punkty stacji |
| `gpx.py` | zapis plików GPX |
| `files.py` | odczyt i atomowy zapis plików |

Lista stacji (`metrorower/resources/stations.json`) zawiera wyłącznie
numery i współrzędne, bez danych o rowerach i ich dostępności.

## Licencja

[MIT](LICENSE)
