import { useState, useEffect } from "react";

export interface GeoState {
  loading: boolean;
  lat: number | null;
  lng: number | null;
  label: string | null;
  error: string | null;
}

/**
 * Déclenche automatiquement la géolocalisation navigateur dès le montage.
 * Effectue un reverse-geocoding via Nominatim (OSM) pour obtenir le libellé du lieu.
 * En cas d'échec réseau, repli sur les coordonnées brutes.
 */
export function useGeolocation(): GeoState {
  const [state, setState] = useState<GeoState>({
    loading: true,
    lat: null,
    lng: null,
    label: null,
    error: null,
  });

  useEffect(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setState((s) => ({
        ...s,
        loading: false,
        error: "Géolocalisation non disponible sur cet appareil",
      }));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        const { latitude: lat, longitude: lng } = coords;
        setState((s) => ({ ...s, lat, lng }));

        try {
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=16&addressdetails=1`,
            { headers: { "Accept-Language": "fr" } },
          );
          if (!res.ok) throw new Error("Nominatim error");
          const data = (await res.json()) as { display_name?: string };
          setState((s) => ({
            ...s,
            loading: false,
            label: data.display_name ?? `${lat.toFixed(5)}, ${lng.toFixed(5)}`,
          }));
        } catch {
          setState((s) => ({
            ...s,
            loading: false,
            label: `${lat.toFixed(5)}, ${lng.toFixed(5)}`,
          }));
        }
      },
      (err) => {
        const msgs: Record<number, string> = {
          1: "Permission de géolocalisation refusée",
          2: "Position impossible à déterminer",
          3: "Délai de localisation dépassé",
        };
        setState({
          loading: false,
          lat: null,
          lng: null,
          label: null,
          error: msgs[err.code] ?? "Erreur de géolocalisation",
        });
      },
      { timeout: 10_000, maximumAge: 60_000 },
    );
  }, []);

  return state;
}