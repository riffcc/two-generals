//! Benchmarks for the Two Generals Protocol.

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use two_generals::{KeyPair, TwoGenerals};

fn benchmark_key_generation(c: &mut Criterion) {
    c.bench_function("keypair_generation", |b| {
        b.iter(|| black_box(KeyPair::generate()))
    });
}

fn benchmark_signing(c: &mut Criterion) {
    let keypair = KeyPair::generate();
    let message = b"I will attack at dawn if you agree";

    c.bench_function("ed25519_sign", |b| {
        b.iter(|| black_box(keypair.sign(message)))
    });
}

fn benchmark_verification(c: &mut Criterion) {
    let keypair = KeyPair::generate();
    let message = b"I will attack at dawn if you agree";
    let signature = keypair.sign(message);

    c.bench_function("ed25519_verify", |b| {
        b.iter(|| black_box(keypair.verify(message, &signature)))
    });
}

fn benchmark_protocol_completion(c: &mut Criterion) {
    c.bench_function("protocol_full_run", |b| {
        b.iter(|| {
            let alice_keys = KeyPair::generate();
            let bob_keys = KeyPair::generate();

            let mut alice = TwoGenerals::new(
                alice_keys.clone(),
                bob_keys.public_key().clone(),
                b"attack at dawn",
            );
            let mut bob = TwoGenerals::new(
                bob_keys.clone(),
                alice_keys.public_key().clone(),
                b"attack at dawn",
            );

            // Run until both complete
            for _ in 0..20 {
                let alice_msgs = alice.get_messages_to_send();
                let bob_msgs = bob.get_messages_to_send();

                for msg in alice_msgs {
                    let _ = bob.receive(&msg);
                }
                for msg in bob_msgs {
                    let _ = alice.receive(&msg);
                }

                if alice.is_complete() && bob.is_complete() {
                    break;
                }
            }

            black_box((alice.can_attack(), bob.can_attack()))
        })
    });
}

criterion_group!(
    benches,
    benchmark_key_generation,
    benchmark_signing,
    benchmark_verification,
    benchmark_protocol_completion,
);
criterion_main!(benches);
