//! Adaptive Flood Controller
//!
//! Implements rate modulation for the adaptive flooding protocol.
//! The controller dynamically adjusts flood rates based on data needs and network conditions.

use std::time::{Duration, Instant};

/// Adaptive flood rate controller.
///
/// Manages the current flood rate and modulates it based on application needs.
#[derive(Debug, Clone)]
pub struct AdaptiveFloodController {
    /// Minimum packets per second (drip mode)
    pub min_rate: u64,
    /// Maximum packets per second (burst mode)
    pub max_rate: u64,
    /// Current flood rate in packets per second
    pub current_rate: u64,
    /// Ramp-up acceleration in packets/sec²
    pub ramp_up: u64,
    /// Ramp-down deceleration in packets/sec²
    pub ramp_down: u64,
    /// Target rate from application feedback
    pub target_rate: u64,
}

impl AdaptiveFloodController {
    /// Create a new adaptive flood controller.
    ///
    /// # Arguments
    ///
    /// * `min_rate` - Minimum packets per second (drip mode)
    /// * `max_rate` - Maximum packets per second (burst mode)
    ///
    /// # Returns
    ///
    /// A new `AdaptiveFloodController` initialized to minimum rate.
    #[must_use]
    pub fn new(min_rate: u64, max_rate: u64) -> Self {
        // Validate inputs
        assert!(min_rate > 0, "Minimum rate must be greater than 0");
        assert!(max_rate >= min_rate, "Maximum rate must be >= minimum rate");

        Self {
            min_rate,
            max_rate,
            current_rate: min_rate,
            // Ramp up: 10% of max per second for smooth acceleration
            ramp_up: max_rate / 10,
            // Ramp down: slow decay to minimum
            ramp_down: min_rate,
            target_rate: min_rate,
        }
    }

    /// Modulate the current rate based on data needs.
    ///
    /// # Arguments
    ///
    /// * `data_needed` - Whether data transfer is active
    ///
    /// # Returns
    ///
    /// The updated current rate.
    pub fn modulate_rate(&mut self, data_needed: bool) -> u64 {
        // Set target based on data needs
        self.target_rate = if data_needed {
            self.max_rate
        } else {
            self.min_rate
        };

        // Exponential ramp up when data is needed
        if data_needed && self.current_rate < self.target_rate {
            self.current_rate = std::cmp::min(
                self.current_rate + self.ramp_up,
                self.target_rate,
            );
        }
        // Linear ramp down when idle
        else if !data_needed && self.current_rate > self.target_rate {
            self.current_rate = std::cmp::max(
                self.current_rate - self.ramp_down,
                self.target_rate,
            );
        }

        self.current_rate
    }

    /// Get the current flood interval.
    ///
    /// # Returns
    ///
    /// Duration between packets at the current rate.
    #[must_use]
    pub fn get_interval(&self) -> Duration {
        Duration::from_secs_f64(1.0 / self.current_rate as f64)
    }
}

/// Adaptive flooder that controls when messages should be sent.
///
/// Wraps the flood controller and tracks timing to determine when to send packets.
#[derive(Debug)]
pub struct AdaptiveFlooder {
    /// The rate controller
    controller: AdaptiveFloodController,
    /// Timestamp of last sent packet
    last_send: Instant,
    /// Total packets sent
    packet_count: u64,
}

impl AdaptiveFlooder {
    /// Create a new adaptive flooder.
    ///
    /// # Arguments
    ///
    /// * `min_rate` - Minimum packets per second (drip mode)
    /// * `max_rate` - Maximum packets per second (burst mode)
    ///
    /// # Returns
    ///
    /// A new `AdaptiveFlooder` ready to control send timing.
    #[must_use]
    pub fn new(min_rate: u64, max_rate: u64) -> Self {
        let mut flooder = Self {
            controller: AdaptiveFloodController::new(min_rate, max_rate),
            last_send: Instant::now(),
            packet_count: 0,
        };
        // Initialize last_send to allow immediate first send
        flooder.last_send = flooder.last_send - Duration::from_secs(1);
        flooder
    }

    /// Check if a packet should be sent now.
    ///
    /// # Arguments
    ///
    /// * `data_pending` - Whether there is data waiting to be sent
    ///
    /// # Returns
    ///
    /// `true` if a packet should be sent now, `false` otherwise.
    pub fn should_send(&mut self, data_pending: bool) -> bool {
        let now = Instant::now();
        let elapsed = now.duration_since(self.last_send);

        // Modulate rate based on data needs
        self.controller.modulate_rate(data_pending);

        // Calculate if we should send now
        let interval = self.controller.get_interval();

        if elapsed >= interval {
            self.last_send = now;
            self.packet_count += 1;
            return true;
        }

        false
    }

    /// Get the current flood rate.
    ///
    /// # Returns
    ///
    /// Current packets per second.
    #[must_use]
    pub fn current_rate(&self) -> u64 {
        self.controller.current_rate
    }

    /// Get the total number of packets sent.
    ///
    /// # Returns
    ///
    /// Total packet count.
    #[must_use]
    pub fn packet_count(&self) -> u64 {
        self.packet_count
    }

    /// Reset the packet counter.
    pub fn reset_counter(&mut self) {
        self.packet_count = 0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread::sleep;

    #[test]
    fn test_controller_initialization() {
        let controller = AdaptiveFloodController::new(1, 1000);
        assert_eq!(controller.min_rate, 1);
        assert_eq!(controller.max_rate, 1000);
        assert_eq!(controller.current_rate, 1);
        assert_eq!(controller.target_rate, 1);
    }

    #[test]
    fn test_controller_ramp_up() {
        let mut controller = AdaptiveFloodController::new(1, 1000);

        // Initially at min rate
        assert_eq!(controller.current_rate, 1);

        // Ramp up with data needed
        controller.modulate_rate(true);
        assert!(controller.current_rate > 1);

        // Continue ramping up
        let rate1 = controller.current_rate;
        controller.modulate_rate(true);
        let rate2 = controller.current_rate;
        assert!(rate2 > rate1);
    }

    #[test]
    fn test_controller_ramp_down() {
        let mut controller = AdaptiveFloodController::new(1, 1000);

        // Ramp up to max
        for _ in 0..20 {
            controller.modulate_rate(true);
        }
        assert_eq!(controller.current_rate, 1000);

        // Now ramp down
        controller.modulate_rate(false);
        let rate1 = controller.current_rate;
        assert!(rate1 < 1000);

        controller.modulate_rate(false);
        let rate2 = controller.current_rate;
        assert!(rate2 < rate1);
    }

    #[test]
    fn test_controller_bounds() {
        let mut controller = AdaptiveFloodController::new(10, 1000);

        // Ramp up - should not exceed max
        for _ in 0..100 {
            controller.modulate_rate(true);
        }
        assert_eq!(controller.current_rate, 1000);

        // Ramp down - should not go below min
        for _ in 0..100 {
            controller.modulate_rate(false);
        }
        assert_eq!(controller.current_rate, 10);
    }

    #[test]
    fn test_flooder_should_send() {
        let mut flooder = AdaptiveFlooder::new(50, 1000); // Use moderate rate for test

        // First call should send immediately
        assert!(flooder.should_send(true), "First send should succeed");
        assert_eq!(flooder.packet_count(), 1);

        // Second call - wait enough time for next send at 50 pkt/sec (20ms interval)
        std::thread::sleep(Duration::from_millis(25));
        assert!(flooder.should_send(true), "Second send should succeed after waiting");
        assert_eq!(flooder.packet_count(), 2);
    }

    #[test]
    fn test_flooder_rate_modulation() {
        let mut flooder = AdaptiveFlooder::new(1, 1000);

        // Start with data pending - should ramp up
        for _ in 0..10 {
            let _ = flooder.should_send(true);
            sleep(Duration::from_millis(10));
        }

        let rate_with_data = flooder.current_rate();
        assert!(rate_with_data > 1, "Rate should increase with data pending");

        // Now without data - should ramp down
        for _ in 0..10 {
            let _ = flooder.should_send(false);
            sleep(Duration::from_millis(10));
        }

        let rate_without_data = flooder.current_rate();
        assert!(rate_without_data < rate_with_data, "Rate should decrease without data");
    }

    #[test]
    fn test_interval_calculation() {
        let controller = AdaptiveFloodController::new(1, 1000);

        // At 1 pkt/sec, interval should be ~1 second
        let interval = controller.get_interval();
        assert!(interval.as_secs_f64() >= 0.9);
        assert!(interval.as_secs_f64() <= 1.1);

        // At 1000 pkt/sec, interval should be ~1ms
        let mut controller = AdaptiveFloodController::new(1, 1000);
        controller.current_rate = 1000;
        let interval = controller.get_interval();
        assert!(interval.as_secs_f64() >= 0.0009);
        assert!(interval.as_secs_f64() <= 0.0011);
    }

    #[test]
    #[should_panic(expected = "Minimum rate must be greater than 0")]
    fn test_invalid_min_rate() {
        let _ = AdaptiveFloodController::new(0, 1000);
    }

    #[test]
    #[should_panic(expected = "Maximum rate must be >= minimum rate")]
    fn test_invalid_max_rate() {
        let _ = AdaptiveFloodController::new(100, 10);
    }
}
