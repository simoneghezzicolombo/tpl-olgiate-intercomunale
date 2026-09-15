# Google Maps Popular Times — Olgiate-Calco-Brivio FS

## Purpose

This folder records a user-captured external signal about the **time-of-day activity profile** around Olgiate-Calco-Brivio railway station. The source is the Google Maps *Popular times* graphic captured on **2026-09-15 at about 21:24 local time**.

This evidence is useful only as a **qualitative / semi-quantitative plausibility check for service-span and peak/off-peak timetable design**. It is not a passenger-count dataset and must not be used as an absolute or directional demand estimate.

## Captured weekdays

The supplied screenshots cover:

- Monday
- Tuesday
- Friday
- Saturday
- Sunday

Wednesday and Thursday were not supplied and are therefore **not observed**. Do not interpolate or infer them as measured data.

The visible hourly bars run from approximately **04:00 through 03:00 the following day**.

## Digitised table

`popular_times_digitised.csv` is a graphical digitisation of the visible bar heights.

Fields:

- `weekday`: weekday displayed by Google Maps;
- `hour_local`: hour represented by the bar;
- `bar_height_px`: approximate rendered height of the bar in the supplied screenshot, in pixels;
- `within_day_typical_index_0_100`: bar height normalised to the tallest non-live bar of that same weekday, where 100 is the within-day peak;
- `live_overlay`: `true` where Google Maps displayed the current-hour LIVE overlay rather than an ordinary typical bar;
- `source_file`: stable descriptive filename assigned to the supplied screenshot.

The normalised index is deliberately **within-day only**. It does not assume that Google uses a common absolute scale across weekdays.

On Tuesday at 21:00 Google Maps displayed `Live 9 pm — Not too busy`. That bar is marked `live_overlay=true` and its normalised typical index is left blank because the screenshot does not establish that the live value is the normal Tuesday profile for 21:00.

## What the screenshots support

Without treating the bars as passenger counts, the observed profiles support the following descriptive reading:

- observed weekdays show a clear morning concentration around **07:00–08:00**;
- Monday, Tuesday and Friday show another strong concentration around **17:00–19:00**;
- the central part of the day remains active but generally below the commuter peaks in the observed weekdays;
- Saturday is flatter, with substantial daytime activity and a later-afternoon / early-evening maximum;
- Sunday is much weaker in the morning and builds gradually toward an evening maximum around **18:00–20:00**.

This makes the source potentially useful when testing whether a fixed `H30/10h` envelope should instead be redistributed over a longer daily span, for example by preserving H30 in observed high-activity windows and using H60 in lower-activity periods.

## Hard limitations

The source does **not** establish:

- absolute station users, boardings or alightings;
- bus demand;
- origin-destination flows;
- direction of rail travel;
- whether people visible to Google's activity model are rail passengers;
- representative sample size;
- the underlying Google estimation methodology;
- exact comparability of bar magnitude between weekdays;
- a causal relationship between station activity and feeder-bus demand.

Accordingly this source must not become a hard candidate filter, a Pareto objective, a demand weight or a justification for selecting a timetable by itself.

Use it as an **external temporal plausibility signal** alongside certified rail timetables, existing bus service, operational runtime/dwell evidence and any future observed passenger data.

## Provenance

Original user-supplied screenshot SHA256 values:

- Tuesday: `fe5b8ef2f9709abc283c5d3769ffb1577bb2934746033fd28e2708ede9fa8534`
- Sunday: `0eb0bd4199855c1f851ad01f6bd7c0191ccf382c20843d993998b2ca00e92241`
- Monday: `295bb45042de88fb58a723a7e37aa902a74a7197c9f4e46e8da0ddb34f1bb3ef`
- Friday: `cef740a1fbbe574bafff661ba7c4e77e5255b6f71d61b63e31da0a86b5761f5a`
- Saturday: `f72ede76945897e28297ae3d23aaf3ed6d381de032eaf6b483062c2b9fe4f1ba`

`source_file` names in the CSV are descriptive aliases for these five captured screenshots. The screenshots themselves are the primary visual evidence; the CSV is a derived approximation.