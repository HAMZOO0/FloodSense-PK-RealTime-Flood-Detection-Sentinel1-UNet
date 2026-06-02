import { useState } from "react";
import { Pressable, StyleSheet, Switch, Text, View } from "react-native";
import { colors, radius, spacing, typography } from "../../theme/tokens";

export function SettingsScreen() {
  const [smsEnabled, setSmsEnabled] = useState(true);
  const [emailEnabled, setEmailEnabled] = useState(true);

  return (
    <View style={styles.root}>
      <Text style={styles.title}>Notification Settings</Text>
      <View style={styles.card}>
        <View style={styles.row}>
          <Text style={styles.label}>SMS Alerts</Text>
          <Switch value={smsEnabled} onValueChange={setSmsEnabled} />
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>Email Alerts</Text>
          <Switch value={emailEnabled} onValueChange={setEmailEnabled} />
        </View>
      </View>
      <Pressable style={styles.logoutBtn}>
        <Text style={styles.logoutText}>Logout</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.bg,
    padding: spacing.xl,
    gap: spacing.md
  },
  title: {
    color: colors.textPrimary,
    fontSize: 20,
    fontWeight: "700",
    fontFamily: typography.mono
  },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.md
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center"
  },
  label: {
    color: colors.textPrimary,
    fontFamily: typography.mono
  },
  logoutBtn: {
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderRadius: radius.md,
    borderColor: colors.accentHigh,
    borderWidth: 1
  },
  logoutText: {
    color: colors.accentHigh,
    fontFamily: typography.mono,
    fontWeight: "700"
  }
});
