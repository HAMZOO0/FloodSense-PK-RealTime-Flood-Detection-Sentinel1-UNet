import { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { colors, radius, spacing, typography } from "../../theme/tokens";
import { AuthStackParamList } from "../../navigation/types";

type Props = NativeStackScreenProps<AuthStackParamList, "Login">;

export function LoginScreen({ navigation }: Props) {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");

    return (
        <View style={styles.root}>
            <Text style={styles.heading}>FloodSense Login</Text>
            <TextInput
                style={styles.input}
                placeholder="Email"
                placeholderTextColor={colors.textMuted}
                value={email}
                autoCapitalize="none"
                keyboardType="email-address"
                onChangeText={setEmail}
            />
            <TextInput
                style={styles.input}
                placeholder="Password"
                placeholderTextColor={colors.textMuted}
                value={password}
                secureTextEntry
                onChangeText={setPassword}
            />
            <Pressable style={styles.primaryBtn}>
                <Text style={styles.primaryBtnText}>Sign In</Text>
            </Pressable>
            <Pressable onPress={() => navigation.navigate("Signup")}>
                <Text style={styles.link}>Create account</Text>
            </Pressable>
        </View>
    );
}

const styles = StyleSheet.create({
    root: {
        flex: 1,
        backgroundColor: colors.bg,
        padding: spacing.xl,
        justifyContent: "center",
        gap: spacing.md,
    },
    heading: {
        color: colors.textPrimary,
        fontSize: 24,
        fontWeight: "700",
        fontFamily: typography.mono,
    },
    input: {
        backgroundColor: colors.surface,
        borderWidth: 1,
        borderColor: colors.border,
        color: colors.textPrimary,
        borderRadius: radius.md,
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
        fontFamily: typography.mono,
    },
    primaryBtn: {
        backgroundColor: colors.accentInfo,
        borderRadius: radius.md,
        alignItems: "center",
        paddingVertical: spacing.sm,
    },
    primaryBtnText: {
        color: "#02131F",
        fontWeight: "700",
        fontFamily: typography.mono,
    },
    link: {
        color: colors.textMuted,
        textAlign: "center",
        fontFamily: typography.mono,
    },
});
