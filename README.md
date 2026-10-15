# Eksport przejazdów Nextbike do GPX

Skrypt pobiera szczegóły przejazdów z API Nextbike i zapisuje:

- pełną odpowiedź API w `data/<ID>.json`,
- ślad trasy w `gpx/YYYYMMDD_metrorower_<ID>.gpx`, gdzie data oznacza
  lokalną datę rozpoczęcia przejazdu w strefie `Europe/Warsaw`.

Ślad jest przycinany do punktów najbliższych stacji startowej i końcowej
z `resources/stations.json`. Pierwsze punkty bywają odległe od stacji, bo GPS
nie złapał jeszcze pozycji, więc ślad zaczyna się od punktu trasy najbliższego
stacji (szukanego w pierwszych 120 s przejazdu), a kończy na punkcie najbliższym
stacji końcowej (w ostatnich 120 s). Na początku i końcu śladu dopisywane są
dokładne współrzędne stacji z czasem wypożyczenia i zwrotu. Gdy odpowiedź API zawiera numer stacji, skrypt używa go do dopasowania.
W pozostałych przypadkach wybiera najbliższą stację (do 300 m) względem
współrzędnych miejsca startu/końca lub punktu trasy.
Plik `resources/stations.json` zawiera wyłącznie numery i współrzędne stacji,
bez danych o rowerach i ich bieżącej dostępności. Można wskazać inny plik
przez `--stations`.

Plik JSON jest jednocześnie cache'em. Jeżeli dane danego ID zostały już
pobrane, API nie zostanie ponownie wywołane. Przejazdy krótsze niż 1 km
pozostają w cache'u, ale nie są eksportowane do GPX.

## Przygotowanie

Wklej do pliku `cookie.txt` całą wartość cookie, w jednej z postaci:

```text
nextbike-react=Fe26.2*...
```

albo samą wartość zaczynającą się od `Fe26.2`.

Do `ids.txt` wklej identyfikatory, po jednym w wierszu. Opcjonalny nagłówek
`ID`, puste wiersze i powtórzenia są ignorowane:

```text
ID
360039555
359818673
```

Oba pliki oraz pobrane dane są ignorowane przez Git, ponieważ zawierają
dane prywatne.

## Uruchomienie

```bash
uv run python nextbike_to_gpx.py
```

Opcjonalne argumenty można zobaczyć poleceniem:

```bash
uv run python nextbike_to_gpx.py --help
```

Wygaśnięcie sesji jest raportowane jako błąd HTTP 401. Wtedy należy
ponownie skopiować cookie po zalogowaniu do serwisu Nextbike.

## Testy

```bash
uv run pytest
```

## Struktura kodu

- `nextbike_to_gpx.py` — punkt wejścia,
- `metrorower/cli.py` — argumenty i przebieg eksportu,
- `metrorower/nextbike.py` — API Nextbike i cache odpowiedzi,
- `metrorower/models.py` — typy danych i walidacja wartości,
- `metrorower/stations.py` — stacje i odległości,
- `metrorower/track.py` — przycinanie śladu i punkty stacji,
- `metrorower/gpx.py` — zapis plików GPX,
- `metrorower/files.py` — odczyt i atomowy zapis plików.
