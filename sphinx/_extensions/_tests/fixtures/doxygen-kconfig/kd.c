/** @file */

/**
 * @defgroup kd_suite Kconfig-dependent test cases
 * @{
 */

/**
 * @brief One condition, next to a test id and a requirement.
 * @kconfig_depends{CONFIG_ASSERT}
 * @reqref{REQ-1}
 * @testid{TC-KD-001}
 */
void test_one(void) {}

/**
 * @brief Two adjacent commands.
 * @kconfig_depends{defined(CONFIG_HW_STACK_PROTECTION) && !defined(CONFIG_ARCH_POSIX)}
 * @kconfig_depends{CONFIG_USERSPACE}
 * @testid{TC-KD-002}
 */
void test_two(void) {}

/**
 * @brief Operators and parentheses.
 * @kconfig_depends{(CONFIG_A && !CONFIG_B) || CONFIG_C}
 * @testid{TC-KD-003}
 */
void test_three(void) {}

/**
 * @brief Details ending in a list.
 *
 * Expected result:
 * - a
 * - b
 *
 * @kconfig_depends{CONFIG_X}
 */
void test_four(void) {}

/**
 * @brief Commands that are not adjacent.
 *
 * @kconfig_depends{CONFIG_FIRST}
 *
 * Some prose between them.
 *
 * @kconfig_depends{IS_ENABLED(CONFIG_A\, CONFIG_B)}
 * @testid{TC-KD-005}
 */
void test_five(void) {}

/**
 * @brief No condition.
 * @reqref{REQ-2}
 */
void test_six(void) {}

/** @} */
