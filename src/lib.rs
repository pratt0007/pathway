// Copyright © 2024 Pathway

#![warn(clippy::pedantic)]
#![warn(clippy::cargo)]
#![allow(clippy::must_use_candidate)] // too noisy

// FIXME:
#![allow(clippy::missing_errors_doc)]
#![allow(clippy::missing_panics_doc)]

pub mod connectors;
pub mod deepcopy;
pub mod engine;
pub mod persistence;
pub mod python_api;

mod fs_helpers;
mod mat_mul;
mod pipe;
mod timestamp;

#[cfg(not(feature = "standard-allocator"))]
mod jemalloc {
    use jemallocator::Jemalloc;

    #[global_allocator]
    static GLOBAL_ALLOCATOR: Jemalloc = Jemalloc;
}
