import { DistrictName } from "../constants/districts";

export type AuthStackParamList = {
  Login: undefined;
  Signup: undefined;
  Otp: { phoneNumber: string; district: DistrictName };
};

export type MainTabParamList = {
  Dashboard: undefined;
  Report: undefined;
  Settings: undefined;
};
