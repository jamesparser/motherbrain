; Motherbrain plugin for Omega: one shared brain for the whole agent fleet.
;
; Adds four skills (mb-recall, mb-remember, mb-lesson, mb-outcome) and keeps the
; shared soul (tone + hard lessons) live in the prompt as a prompt extension.
; When the soul changes (any agent writes a lesson, mood shifts, a dream runs)
; the heartbeat swaps the extension in place: "RE-READ motherbrain.md" with no reboot.
;
; Enable on the Omega command line (env is dropped when Omega switches user):
;   motherbrainEnabled=enabled motherbrainURL=http://<host>:8790 motherbrainAgent=omega
; Token: plugins/motherbrain/.token (MB_API_KEY), mounted read-only.
!(import! &self (library Omega ./plugins/motherbrain/motherbrain.py))

(= (motherbrainEnabled) (empty))
(= (motherbrainURL) (empty))
(= (motherbrainAgent) (empty))

(= (loadOmegaPlugin)
    (progn
        (configure motherbrainEnabled disabled)
        (configure motherbrainURL "")
        (configure motherbrainAgent "omega")
        (if (== (motherbrainEnabled) enabled)
            (if (== (motherbrainURL) "")
                (Error (_loadOmegaPlugin) "Motherbrain is enabled, but motherbrainURL is not configured")
                (progn
                    (log INFO "motherbrain-plugin" "Motherbrain shared brain is enabled")
                    (add-skill mb-recall
                        "Recall from the shared Motherbrain: memories and hard lessons learned by every agent in the fleet. Use before planning any non-trivial task"
                        (query))
                    (add-skill mb-remember
                        "Save a durable fact to the shared Motherbrain so every agent in the fleet knows it"
                        (text))
                    (add-skill mb-lesson
                        "Record a hard lesson for the whole fleet after a costly mistake: when TRIGGER happens, do RULE"
                        (trigger rule))
                    (add-skill mb-outcome
                        "Report how a task ended to the shared Motherbrain; outcome is ok or fail"
                        (task outcome))
                    (py-call (motherbrain.join (motherbrainURL) (motherbrainAgent)))
                    (motherbrain-sync-soul)
                    (add-heartbeat-listener motherbrain (|-> ($iter) (motherbrain-sync-soul)))))
            (log INFO "motherbrain-plugin" "Motherbrain shared brain is disabled"))))

(= (mb-recall $query)
    (py-call (motherbrain.recall $query (motherbrainURL) (motherbrainAgent))))

(= (mb-remember $text)
    (py-call (motherbrain.remember $text (motherbrainURL) (motherbrainAgent))))

(= (mb-lesson $trigger $rule)
    (py-call (motherbrain.lesson $trigger $rule (motherbrainURL) (motherbrainAgent))))

(= (mb-outcome $task $outcome)
    (py-call (motherbrain.outcome $task $outcome (motherbrainURL) (motherbrainAgent))))

; Python side throttles (one HTTP check per minute) and returns "" when unchanged.
(= (motherbrain-sync-soul)
    (let $soul (py-call (motherbrain.soul_if_changed (motherbrainURL)))
        (if (> (string_length $soul) 0)
            (progn
                (remove-prompt-extension motherbrain_soul)
                (add-prompt-extension motherbrain_soul $soul))
            ())))
