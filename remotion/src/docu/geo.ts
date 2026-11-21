import {feature} from 'topojson-client';
import type {Feature, FeatureCollection, Geometry} from 'geojson';
import world50 from 'world-atlas/countries-50m.json';
import world110 from 'world-atlas/countries-110m.json';

export type Country = Feature<Geometry, {name: string}>;

const toFc = (topo: any): FeatureCollection<Geometry, {name: string}> =>
  feature(topo, topo.objects.countries) as unknown as FeatureCollection<Geometry, {name: string}>;

let cache50: Country[] | null = null;
let cache110: Country[] | null = null;

/** Natural Earth country shapes (public domain) via the world-atlas package. */
export const countries = (detail: 'high' | 'low' = 'high'): Country[] => {
  if (detail === 'low') return (cache110 ??= toFc(world110).features);
  return (cache50 ??= toFc(world50).features);
};

const ALIASES: Record<string, string> = {
  usa: 'United States of America', us: 'United States of America', 'united states': 'United States of America',
  uk: 'United Kingdom', britain: 'United Kingdom', 'great britain': 'United Kingdom', drc: 'Dem. Rep. Congo',
  'south korea': 'South Korea', 'north korea': 'North Korea', 'czech republic': 'Czechia', 'ivory coast': "Côte d'Ivoire",
};

export const findCountry = (name: string, list: Country[]): Country | undefined => {
  const n = (ALIASES[name.toLowerCase()] ?? name).toLowerCase();
  return list.find((c) => c.properties.name.toLowerCase() === n) ?? list.find((c) => c.properties.name.toLowerCase().startsWith(n));
};
