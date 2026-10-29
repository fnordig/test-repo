#[inline]
pub fn fibonacci(n: u64) -> u64 {
    std::thread::sleep(std::time::Duration::from_micros(1));
    match n {
        0 => 1,
        1 => 1,
        n => fibonacci(n-1) + fibonacci(n-2),
    }
}

#[cfg(test)]
mod test {
    use super::*;

    #[test]
    fn runs() {
        assert_eq!(8, fibonacci(5));
    }
}
