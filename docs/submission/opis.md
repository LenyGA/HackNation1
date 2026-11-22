# RolnikSzukaWody — opis zgłoszenia (Z2)

**Zespół:** GeoSatel · **Tytuł:** RolnikSzukaWody · **Zadanie:** KOWR „Zatrzymaj wodę, chroń plony”
**Działająca wersja:** https://129.121.162.156.sslip.io

*Szkic do wklejenia na Platformę. Zespół: skrócić do limitu znaków z formularza.*

## Problem

Susza rolnicza w Polsce wraca coraz częściej, a rolnik nie ma prostego sposobu, żeby sprawdzić, czy jego pole ma za mało wody,
dlaczego tak jest i co może zrobić. Dane, które na to odpowiadają, są publiczne: pogoda, satelity, mapy gleb, model terenu,
rowy i cieki, strefy powodziowe, wody gruntowe. Są jednak rozproszone w kilkunastu serwisach i wymagają wiedzy GIS.

## Główne funkcje

- Wybór działki numerem ewidencyjnym, kliknięciem na mapie albo adresem; do 5 sąsiednich działek gospodarstwa.
- Wybór uprawy (13 pozycji, w tym sady i krzewy owocowe) i daty analizy: dziś lub dowolny dzień z ostatnich 10 lat.
- Ocena sytuacji wodnej na dzień analizy: zapas wody w glebie i próg, poniżej którego uprawa cierpi, bilans opadu i parowania na tle
  10 lat, oficjalny próg suszy rolniczej IUNG-PIB, kondycja roślin z satelity, wody gruntowe.
- Podatność wieloletnia: w ilu latach było za sucho, trendy klimatu na działce, zagrożenie powodzią i podtopieniami.
- Przyczyny niedoboru z dowodem liczbowym, a potem działania w kolejności z zadania: retencja (5 metod ze statusem
  POLECANE / WARUNKOWO / NIEZALECANE / BRAK DANYCH i formalnościami z Prawa wodnego), agrotechnika, nawadnianie (termin, dawka, dobór
  technologii, opłacalność), symulator strategii na 1–5 lat.
- Raport Podstawowy (1–2 strony) i Pełny, zapisany pod stałym linkiem, PDF i druk. Każda liczba ma źródło i datę, a braki
  danych i ograniczenia są podane wprost.

## Wykorzystanie danych

Aplikacja w chwili analizy pobiera 9 źródeł publicznych, z czego 8 równolegle (GUGiK ULDK i NMT 1 m; Open-Meteo / ERA5
z zapasem NASA POWER; Sentinel-2; SoilGrids; ESA WorldCover; OpenStreetMap; Wody Polskie ISOK; PIG-PIB) i **liczy** wynik
według uznanej metodyki: bilans FAO-56 (Penman–Monteith, Kc uprawy), progi KBW IUNG-PIB z rozporządzenia (Dz.U. 2019
poz. 739), retencja wody w glebie ze składu gleby, zagłębienia i spływ z modelu terenu, NWRM dla retencji. Każde zalecenie
wynika z reguły, która sprawdza wartości policzone dla tej działki i tej daty. Bez LLM i bez gotowych tekstów: ten sam zestaw
danych zawsze daje ten sam raport. Awaria źródła obniża pewność wyniku i jest opisana w raporcie, ale nie przerywa analizy.

## Korzyści dla użytkownika

- Odpowiedź w kilkanaście sekund, bez konta, instalacji, opłat i wiedzy GIS; działa na telefonie w polu.
- Konkretne działania dla tej działki: gdzie zatrzymać wodę, co zmienić w uprawie, czy i jak opłaca się nawadniać.
- Rozdzielenie bieżącej suszy od trwałej podatności pola, więc decyzje doraźne i inwestycyjne są osobno.
- Jawna niepewność i źródła, dzięki czemu doradca ODR lub urzędnik może sprawdzić każdą liczbę.
