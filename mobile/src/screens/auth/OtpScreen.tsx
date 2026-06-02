import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { AuthStackParamList } from "../../navigation/types";
import { colors, radius, spacing, typography } from "../../theme/tokens";

type Props = NativeStackScreenProps<AuthStackParamList, "Otp">;

export function OtpScreen({ route }: Props) {
  const { phoneNumber, district } = route.params;
  const [otp, setOtp] = useState("");

  return (
    <View style={styles.root}>
      <Text style={styles.heading}>Verify OTP</Text>
      <Text style={styles.caption}>Phone: {phoneNumber || "N/A"}</Text>
      <Text style={styles.caption}>District: {district}</Text>
      <TextInput
        style={styles.otpInput}
        value={otp}
        onChangeText={setOtp}
        keyboardType="number-pad"
        maxLength={6}
        placeholder="123456"
        placeholderTextColor={colors.textMuted}
      />
      <Pressable style={styles.primaryBtn}>
        <Text style={styles.primaryBtnText}>Confirm OTP</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.bg,
    padding: spacing.xl,
    gap: spacing.md,
    justifyContent: "center"
  },
  heading: {
    color: colors.textPrimary,
    fontSize: 24,
    fontWeight: "700",
    fontFamily: typography.mono
  },
  caption: {
    color: colors.textMuted,
    fontFamily: typography.mono
  },
  otpInput: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: radius.md,
    color: colors.textPrimary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    letterSpacing: 8,
    textAlign: "center",
    fontFamily: typography.mono,
    fontSize: 20
  },
  primaryBtn: {
    backgroundColor: colors.accentWarning,
    borderRadius: radius.md,
    alignItems: "center",
    paddingVertical: spacing.sm
  },
  primaryBtnText: {
    color: "#1A1000",
    fontWeight: "700",
    fontFamily: typography.mono
  }
});
