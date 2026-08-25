import { useState, useEffect } from 'react';
import { api } from './api';

export interface GeoLocationInfo {
  ip: string;
  country_code: string;
  country_name: string;
  is_nepal: boolean;
  city?: string | null;
  source?: string;
  loading: boolean;
}

let cachedGeo: GeoLocationInfo | null = null;
let geoPromise: Promise<GeoLocationInfo> | null = null;

export async function detectGeoLocation(): Promise<GeoLocationInfo> {
  if (cachedGeo && !cachedGeo.loading) {
    return cachedGeo;
  }

  // Check if browser timezone is Kathmandu/Nepal as an initial fast check
  let initialNepalGuess = false;
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone.toLowerCase();
    if (tz.includes('kathmandu') || tz.includes('nepal')) {
      initialNepalGuess = true;
    }
  } catch {
    // Ignore timezone failure
  }

  if (geoPromise) {
    return geoPromise;
  }

  const fetchPromise = (async (): Promise<GeoLocationInfo> => {
    try {
      // Check session storage first
      if (typeof window !== 'undefined') {
        const stored = sessionStorage.getItem('kds_geo_info');
        if (stored) {
          const parsed = JSON.parse(stored);
          cachedGeo = { ...parsed, loading: false };
          return cachedGeo as GeoLocationInfo;
        }
      }

      const res = await api.get('/geo/lookup', { timeout: 3500 });
      const data = res.data || {};
      
      const isNepal = Boolean(
        data.is_nepal || 
        data.country_code === 'NP' || 
        data.country_code === 'NPL' ||
        initialNepalGuess
      );

      const info: GeoLocationInfo = {
        ip: data.ip || '',
        country_code: isNepal ? 'NP' : (data.country_code || 'UNKNOWN'),
        country_name: isNepal ? 'Nepal' : (data.country_name || 'Unknown'),
        is_nepal: isNepal,
        city: data.city || null,
        source: data.source || 'api',
        loading: false,
      };

      cachedGeo = info;
      if (typeof window !== 'undefined') {
        sessionStorage.setItem('kds_geo_info', JSON.stringify(info));
      }
      return info;
    } catch (err) {
      // Graceful fallback using timezone detection
      const fallback: GeoLocationInfo = {
        ip: '',
        country_code: initialNepalGuess ? 'NP' : 'UNKNOWN',
        country_name: initialNepalGuess ? 'Nepal' : 'Unknown',
        is_nepal: initialNepalGuess,
        loading: false,
        source: 'timezone_fallback',
      };
      cachedGeo = fallback;
      return fallback;
    } finally {
      geoPromise = null;
    }
  })();

  geoPromise = fetchPromise;
  return geoPromise;
}

export function useGeoLocation() {
  const [geo, setGeo] = useState<GeoLocationInfo>(() => {
    if (cachedGeo) return cachedGeo;
    let initialNepal = false;
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone.toLowerCase();
      if (tz.includes('kathmandu') || tz.includes('nepal')) {
        initialNepal = true;
      }
    } catch {}
    return {
      ip: '',
      country_code: initialNepal ? 'NP' : '',
      country_name: initialNepal ? 'Nepal' : '',
      is_nepal: initialNepal,
      loading: true,
    };
  });

  useEffect(() => {
    let mounted = true;
    detectGeoLocation().then((info) => {
      if (mounted) {
        setGeo(info);
      }
    });
    return () => {
      mounted = false;
    };
  }, []);

  return geo;
}
