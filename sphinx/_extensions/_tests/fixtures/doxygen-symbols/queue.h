/**
 * @file queue.h
 * @brief Queue API.
 */

/**
 * @defgroup queue_apis Queue APIs
 * @brief Queue kernel objects.
 * @{
 */

/**
 * @brief Initialize a queue.
 *
 * @param q Address of the queue.
 *
 * @satisfies REQ-QUEUE-1
 */
void k_queue_init(struct k_queue *q);

/**
 * @brief Append an element to the end of a queue.
 *
 * @param q Address of the queue.
 * @param data Address of the data item.
 *
 * @satisfies REQ-QUEUE-1
 * @satisfies REQ-QUEUE-2
 * @kconfig_depends{CONFIG_ASSERT}
 * @kconfig_depends{(CONFIG_USERSPACE && !CONFIG_NO_SYSCALLS) || CONFIG_TEST}
 */
void k_queue_append(struct k_queue *q, void *data);

/**
 * @brief Maximum number of items; references a UID no requirement defines.
 *
 * @satisfies REQ-QUEUE-99
 */
#define K_QUEUE_MAX 8

/**
 * @brief Not annotated: must not become a need.
 */
void k_queue_cancel_wait(struct k_queue *q);

/** @} */

/**
 * @brief Query a queue to see if it has data available; outside any group.
 *
 * @satisfies REQ-QUEUE-2
 */
int k_queue_is_empty(struct k_queue *q);
