import { NavigationContainer, DarkTheme } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { AlertTriangle, FileText, Gauge, LogIn, Settings, UserPlus, ShieldCheck } from "lucide-react-native";
import { useMemo, useState } from "react";
import { Pressable } from "react-native";
import { LoginScreen } from "../screens/auth/LoginScreen";
import { OtpScreen } from "../screens/auth/OtpScreen";
import { SignupScreen } from "../screens/auth/SignupScreen";
import { DashboardScreen } from "../screens/main/DashboardScreen";
import { ReportScreen } from "../screens/main/ReportScreen";
import { SettingsScreen } from "../screens/main/SettingsScreen";
import { colors } from "../theme/tokens";
import { AuthStackParamList, MainTabParamList } from "./types";

const AuthStack = createNativeStackNavigator<AuthStackParamList>();
const MainTabs = createBottomTabNavigator<MainTabParamList>();

function AuthStackNavigator() {
  return (
    <AuthStack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.textPrimary,
        contentStyle: { backgroundColor: colors.bg }
      }}
    >
      <AuthStack.Screen
        name="Login"
        component={LoginScreen}
        options={{ title: "Login", headerRight: () => <LogIn color={colors.textMuted} size={16} /> }}
      />
      <AuthStack.Screen
        name="Signup"
        component={SignupScreen}
        options={{ title: "Signup", headerRight: () => <UserPlus color={colors.textMuted} size={16} /> }}
      />
      <AuthStack.Screen
        name="Otp"
        component={OtpScreen}
        options={{ title: "OTP Verify", headerRight: () => <ShieldCheck color={colors.textMuted} size={16} /> }}
      />
    </AuthStack.Navigator>
  );
}

function MainTabNavigator({ onLogout }: { onLogout: () => void }) {
  return (
    <MainTabs.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.textPrimary,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        tabBarActiveTintColor: colors.textPrimary,
        tabBarInactiveTintColor: colors.textMuted
      }}
    >
      <MainTabs.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{
          tabBarIcon: ({ color, size }) => <Gauge color={color} size={size} />,
          headerRight: () => <AlertTriangle color={colors.accentHigh} size={18} />
        }}
      />
      <MainTabs.Screen
        name="Report"
        component={ReportScreen}
        options={{ tabBarIcon: ({ color, size }) => <FileText color={color} size={size} /> }}
      />
      <MainTabs.Screen
        name="Settings"
        component={SettingsScreen}
        options={{
          tabBarIcon: ({ color, size }) => <Settings color={color} size={size} />,
          headerRight: () => (
            <Pressable onPress={onLogout}>
              <Settings color={colors.textMuted} size={18} />
            </Pressable>
          )
        }}
      />
    </MainTabs.Navigator>
  );
}

export function AppNavigator() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const theme = useMemo(
    () => ({
      ...DarkTheme,
      colors: {
        ...DarkTheme.colors,
        background: colors.bg,
        card: colors.surface,
        border: colors.border,
        text: colors.textPrimary,
        primary: colors.accentInfo
      }
    }),
    []
  );

  return (
    <NavigationContainer theme={theme}>
      {isAuthenticated ? (
        <MainTabNavigator onLogout={() => setIsAuthenticated(false)} />
      ) : (
        <AuthStackNavigator />
      )}
    </NavigationContainer>
  );
}
