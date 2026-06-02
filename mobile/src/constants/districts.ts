export const DISTRICTS = [
  "Swat",
  "Shangla",
  "Kanju",
  "Mingora",
  "Kalam",
  "Behrain",
  "Charsadda",
  "Nowshera",
  "Peshawar",
  "Dera Ismail Khan",
  "Rajanpur",
  "Dera Ghazi Khan",
  "Muzaffargarh",
  "Layyah",
  "Sukkur",
  "Larkana",
  "Shikarpur",
  "Jacobabad",
  "Kashmore",
  "Jafferabad",
  "Naseerabad"
] as const;

export type DistrictName = (typeof DISTRICTS)[number];
