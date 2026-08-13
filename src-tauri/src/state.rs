use crate::recording::Recorder;
use std::sync::Mutex;

#[derive(Default)]
pub struct AppState {
    pub recorder: Mutex<Option<Recorder>>,
}
