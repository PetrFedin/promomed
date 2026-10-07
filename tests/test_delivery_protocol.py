import base64
import importlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import (
    change_impact,
    delivery_protocol,
    evidence_checkpoint,
    evidence_graph,
    evidence_interchange,
    syndication_network,
)
from app.auth import seed_demo_accounts


def _key_b64():
    private=Ed25519PrivateKey.generate()
    raw=private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class PartnerDeliveryProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(
            os.environ,
            {
                "SQLITE_PATH":str(Path(self.tmp.name)/"delivery.db"),
                "PROMOMED_SEED_DEMO":"true",
                "PROMOMED_EVIDENCE_ISSUER_ID":"promomed-delivery-test",
                "PROMOMED_EVIDENCE_KEY_ID":"delivery-key-v1",
                "PROMOMED_EVIDENCE_SIGNING_PRIVATE_KEY_B64":_key_b64(),
                "PROMOMED_WEBHOOK_MASTER_SECRET":"test-webhook-master-secret-"+"x"*40,
            },
            clear=False,
        )
        self.env.start()

        import app.db as db
        importlib.reload(db)
        self.db=db
        self.c=db.connect()
        db.migrate(self.c)
        seed_demo_accounts(self.c)
        evidence_graph.seed_demo(self.c)
        self._register_org()
        self._qualify()
        self.endpoint_registration=self._register_and_verify_endpoint()
        self.secret=self.endpoint_registration["secret"]

    def tearDown(self):
        self.c.close()
        self.env.stop()
        self.tmp.cleanup()

    def _register_org(self):
        evidence_interchange.register_organization(
            self.c,
            organization_id="INST-DELIVERY-001",
            name="Synthetic Delivery Society",
            organization_type="scientific_society",
            actor="governance@demo.ru",
            external_ref="urn:synthetic:delivery:001",
            credential_source="synthetic test fixture",
            demo_only=True,
        )
        for role in ("consumer","contributor"):
            evidence_interchange.bind_role(
                self.c,
                organization_id="INST-DELIVERY-001",
                role_scope=role,
                actor="governance@demo.ru",
                verification_ref="synthetic-role-proof",
                demo_only=True,
            )

    def _qualify(self):
        snapshot=syndication_network.start_qualification(
            self.c,
            "INST-DELIVERY-001",
            "governance@demo.ru",
            validity_seconds=864000,
            demo_only=True,
        )
        qid=snapshot["qualification"]["id"]
        for scope in syndication_network.REQUIRED_CONFORMANCE_SCOPES:
            syndication_network.record_conformance(
                self.c,
                qid,
                scope,
                "passed",
                "governance@demo.ru",
                "urn:test:"+scope,
                "Synthetic conformance evidence.",
            )
        syndication_network.finalize_qualification(
            self.c,qid,"governance@demo.ru",validity_seconds=864000
        )

    def _register_and_verify_endpoint(self):
        registration=delivery_protocol.register_endpoint(
            self.c,
            "INST-DELIVERY-001",
            "https://partner.example.test/promomed",
            "governance@demo.ru",
            demo_only=True,
        )
        secret=registration["secret"]

        def verifier(url,body,headers):
            payload=json.loads(body.decode("utf-8"))
            payload_sha=headers["X-Promomed-Payload-SHA256"]
            self.assertEqual(
                hashlib_sha(body),
                payload_sha,
            )
            self.assertTrue(
                delivery_protocol.verify_signature(
                    secret,
                    int(headers["X-Promomed-Timestamp"]),
                    headers["X-Promomed-Event-Id"],
                    payload_sha,
                    headers["X-Promomed-Signature"],
                )
            )
            return {
                "status":200,
                "body":json.dumps({"challenge":payload["challenge"]}).encode("utf-8"),
            }

        delivery_protocol.verify_endpoint(
            self.c,registration["endpoint"]["id"],"governance@demo.ru",transport=verifier
        )
        return registration

    def _subscribe(self,withdrawal_sla=3600):
        return syndication_network.create_subscription(
            self.c,
            "INST-DELIVERY-001",
            "artifact",
            "content:CT01",
            "governance@demo.ru",
            update_sla_seconds=3600,
            withdrawal_sla_seconds=withdrawal_sla,
        )

    def _package_and_delivery(self):
        evidence_checkpoint.issue(self.c,"content","CT01")
        package=evidence_interchange.create_package(
            self.c,
            artifact_kind="content",
            artifact_ref="CT01",
            actor="governance@demo.ru",
        )
        delivery=evidence_interchange.deliver_package(
            self.c,
            package_id=package["id"],
            organization_id="INST-DELIVERY-001",
            actor="governance@demo.ru",
            delivery_role="consumer",
        )
        return package,delivery

    def _dispatch_success(self,event_id):
        captured={}
        def transport(url,body,headers):
            captured.update(headers)
            return {"status":204,"body":b""}
        result=delivery_protocol.dispatch_event(
            self.c,event_id,transport=transport
        )
        return result,captured

    def _ack(self,event_id,secret=None,timestamp=None):
        event=self.c.execute(
            "SELECT payload_sha256 FROM syndication_delivery_events WHERE id=?",
            (event_id,),
        ).fetchone()
        ack={
            "eventId":event_id,
            "payloadSha256":event["payload_sha256"],
            "status":"accepted",
        }
        timestamp=int(timestamp or time.time())
        signature=delivery_protocol.acknowledgement_signature(
            secret or self.secret,timestamp,event_id,ack
        )
        return delivery_protocol.acknowledge_event(
            self.c,event_id,"INST-DELIVERY-001",ack,timestamp,signature
        )

    def test_endpoint_secret_is_one_time_and_read_projection_is_redacted(self):
        replay=delivery_protocol.register_endpoint(
            self.c,
            "INST-DELIVERY-001",
            "https://partner.example.test/promomed",
            "governance@demo.ru",
            demo_only=True,
        )
        self.assertTrue(replay["idempotentReplay"])
        self.assertIsNone(replay["secret"])
        self.assertFalse(replay["secretIssued"])

        snapshot=delivery_protocol.endpoint_snapshot(self.c,"INST-DELIVERY-001")
        self.assertEqual(len(snapshot),1)
        public=snapshot[0]
        self.assertEqual(public["status"],"active")
        self.assertFalse(public["secretExposed"])
        text=str(public)
        self.assertNotIn("secret_hash",text)
        self.assertNotIn("verification_challenge",text)
        self.assertNotIn(self.secret,text)

    def test_registration_rejects_non_https_and_verification_blocks_private_network(self):
        with self.assertRaisesRegex(ValueError,"webhook_https_required"):
            delivery_protocol.register_endpoint(
                self.c,
                "INST-DELIVERY-001",
                "http://partner.example.test/hook",
                "governance@demo.ru",
                demo_only=True,
            )
        private=delivery_protocol.register_endpoint(
            self.c,
            "INST-DELIVERY-001",
            "https://127.0.0.1/promomed",
            "governance@demo.ru",
            demo_only=True,
        )
        with self.assertRaisesRegex(ValueError,"webhook_endpoint_verification_transport_failed"):
            delivery_protocol.verify_endpoint(
                self.c,private["endpoint"]["id"],"governance@demo.ru"
            )

    def test_package_delivery_auto_enqueues_deterministic_event_and_retry_does_not_duplicate(self):
        self._subscribe()
        package,delivery=self._package_and_delivery()
        outbound=delivery["outboundEvent"]
        self.assertIsNotNone(outbound)
        self.assertEqual(outbound["event_type"],"package_delivery")
        event_id=outbound["id"]

        again=evidence_interchange.deliver_package(
            self.c,
            package_id=package["id"],
            organization_id="INST-DELIVERY-001",
            actor="governance@demo.ru",
            delivery_role="consumer",
        )
        self.assertEqual(again["outboundEvent"]["id"],event_id)
        self.assertTrue(again["outboundEvent"]["idempotentReplay"])

        calls=[]
        def flaky(url,body,headers):
            calls.append(headers["X-Promomed-Event-Id"])
            if len(calls)==1:
                return {"status":503,"body":b"retry"}
            return {"status":204,"body":b""}

        first=delivery_protocol.dispatch_event(self.c,event_id,transport=flaky)
        self.assertEqual(first["transportStatus"],"retryable_failure")
        self.assertEqual(first["eventStatus"],"queued")
        second=delivery_protocol.dispatch_event(
            self.c,event_id,transport=flaky,now=first["nextRetryAt"]
        )
        self.assertEqual(second["transportStatus"],"success")
        self.assertEqual(second["eventStatus"],"delivered")
        self.assertEqual(calls,[event_id,event_id])

        attempts=self.c.execute(
            "SELECT COUNT(*) n FROM syndication_delivery_attempts WHERE event_id=?",
            (event_id,),
        ).fetchone()["n"]
        self.assertEqual(attempts,2)

        with self.assertRaises(Exception):
            self.c.execute(
                "UPDATE syndication_delivery_events SET subject_ref='mutated' WHERE id=?",
                (event_id,),
            )
        self.c.rollback()

    def test_successful_delivery_is_not_redispatched_without_new_business_event(self):
        self._subscribe()
        _,delivery=self._package_and_delivery()
        event_id=delivery["outboundEvent"]["id"]
        first,_=self._dispatch_success(event_id)
        self.assertEqual(first["eventStatus"],"delivered")

        calls=[]
        def should_not_run(url,body,headers):
            calls.append(1)
            return {"status":204,"body":b""}

        replay=delivery_protocol.dispatch_event(
            self.c,event_id,transport=should_not_run
        )
        self.assertTrue(replay["idempotentReplay"])
        self.assertEqual(replay["status"],"delivered")
        self.assertEqual(calls,[])

    def test_ack_survives_secret_rotation_and_advances_cursor_once(self):
        self._subscribe()
        package,delivery=self._package_and_delivery()
        event_id=delivery["outboundEvent"]["id"]
        dispatched,headers=self._dispatch_success(event_id)
        self.assertEqual(dispatched["eventStatus"],"delivered")
        self.assertEqual(headers["X-Promomed-Secret-Version"],"1")

        rotated=delivery_protocol.rotate_endpoint_secret(
            self.c,self.endpoint_registration["endpoint"]["id"],"governance@demo.ru"
        )
        self.assertNotEqual(rotated["secret"],self.secret)
        self.assertEqual(rotated["endpoint"]["secretVersion"],2)

        ack=self._ack(event_id,secret=self.secret)
        self.assertEqual(ack["status"],"acknowledged")
        sequence=self.c.execute(
            "SELECT sequence_no FROM syndication_delivery_events WHERE id=?",
            (event_id,),
        ).fetchone()["sequence_no"]
        self.assertEqual(ack["lastAckedSequence"],sequence)

        replay=self._ack(event_id,secret=self.secret)
        self.assertTrue(replay["idempotentReplay"])
        event=self.c.execute(
            "SELECT payload_sha256 FROM syndication_delivery_events WHERE id=?",
            (event_id,),
        ).fetchone()
        original_ack={
            "eventId":event_id,
            "payloadSha256":event["payload_sha256"],
            "status":"accepted",
        }
        ts=int(time.time())
        with self.assertRaisesRegex(ValueError,"delivery_ack_conflict"):
            delivery_protocol.acknowledge_event(
                self.c,event_id,"INST-DELIVERY-001",original_ack,ts,"v1="+"0"*64
            )
        count=self.c.execute(
            "SELECT COUNT(*) n FROM syndication_delivery_acknowledgements WHERE event_id=?",
            (event_id,),
        ).fetchone()["n"]
        self.assertEqual(count,1)

    def test_queued_event_can_route_through_new_active_endpoint_without_new_event(self):
        self._subscribe()
        _,delivery=self._package_and_delivery()
        event_id=delivery["outboundEvent"]["id"]
        original_endpoint=self.endpoint_registration["endpoint"]["id"]

        delivery_protocol.suspend_endpoint(
            self.c,original_endpoint,"governance@demo.ru","Synthetic endpoint rotation"
        )
        replacement=delivery_protocol.register_endpoint(
            self.c,
            "INST-DELIVERY-001",
            "https://partner2.example.test/promomed",
            "governance@demo.ru",
            demo_only=True,
        )
        replacement_secret=replacement["secret"]

        def verify_replacement(url,body,headers):
            payload=json.loads(body.decode("utf-8"))
            return {
                "status":200,
                "body":json.dumps({"challenge":payload["challenge"]}).encode("utf-8"),
            }

        delivery_protocol.verify_endpoint(
            self.c,replacement["endpoint"]["id"],"governance@demo.ru",
            transport=verify_replacement
        )

        captured={}
        def transport(url,body,headers):
            captured["url"]=url
            captured["headers"]=dict(headers)
            return {"status":204,"body":b""}

        result=delivery_protocol.dispatch_event(
            self.c,event_id,transport=transport
        )
        self.assertEqual(result["eventStatus"],"delivered")
        self.assertEqual(captured["url"],"https://partner2.example.test/promomed")
        attempt=self.c.execute(
            """SELECT endpoint_id FROM syndication_delivery_attempts
               WHERE event_id=? ORDER BY attempt_no DESC LIMIT 1""",
            (event_id,),
        ).fetchone()
        self.assertEqual(attempt["endpoint_id"],replacement["endpoint"]["id"])

        ack=self._ack(event_id,secret=replacement_secret)
        self.assertEqual(ack["status"],"acknowledged")
        event_count=self.c.execute(
            "SELECT COUNT(*) n FROM syndication_delivery_events WHERE id=?",
            (event_id,),
        ).fetchone()["n"]
        self.assertEqual(event_count,1)

    def test_invalid_ack_signature_is_rejected(self):
        self._subscribe()
        _,delivery=self._package_and_delivery()
        event_id=delivery["outboundEvent"]["id"]
        self._dispatch_success(event_id)
        event=self.c.execute(
            "SELECT payload_sha256 FROM syndication_delivery_events WHERE id=?",
            (event_id,),
        ).fetchone()
        ack={
            "eventId":event_id,
            "payloadSha256":event["payload_sha256"],
            "status":"accepted",
        }
        with self.assertRaisesRegex(ValueError,"delivery_ack_signature_invalid"):
            delivery_protocol.acknowledge_event(
                self.c,event_id,"INST-DELIVERY-001",ack,int(time.time()),"v1=bad"
            )

    def test_withdrawal_event_acknowledgement_closes_sla_with_delivery_evidence(self):
        self._subscribe(withdrawal_sla=3600)
        _,delivery=self._package_and_delivery()
        delivery_event=delivery["outboundEvent"]["id"]
        self._dispatch_success(delivery_event)
        self._ack(delivery_event)

        change_impact.analyze_source_change(
            self.c,
            "ES01",
            "source_retracted",
            "Synthetic retraction through delivery protocol",
            "editor@demo.ru",
        )
        withdrawal=self.c.execute(
            """SELECT e.id,e.obligation_id
               FROM syndication_delivery_events e
               WHERE e.organization_id='INST-DELIVERY-001'
                 AND e.event_type='package_withdrawal'
               ORDER BY e.sequence_no DESC LIMIT 1"""
        ).fetchone()
        self.assertIsNotNone(withdrawal)
        self._dispatch_success(withdrawal["id"])
        ack=self._ack(withdrawal["id"])
        self.assertEqual(ack["obligation"]["status"],"acknowledged")
        obligation=self.c.execute(
            "SELECT status,evidence_ref FROM syndication_delivery_obligations WHERE id=?",
            (withdrawal["obligation_id"],),
        ).fetchone()
        self.assertEqual(obligation["status"],"acknowledged")
        self.assertEqual(obligation["evidence_ref"],"delivery-event:"+withdrawal["id"])

    def test_observed_withdrawal_sla_breach_triggers_requalification_not_auto_revocation(self):
        self._subscribe(withdrawal_sla=3600)
        _,delivery=self._package_and_delivery()
        delivery_event=delivery["outboundEvent"]["id"]
        self._dispatch_success(delivery_event)
        self._ack(delivery_event)

        change_impact.analyze_source_change(
            self.c,
            "ES01",
            "source_retracted",
            "Synthetic overdue withdrawal",
            "editor@demo.ru",
        )
        obligation=self.c.execute(
            """SELECT id FROM syndication_delivery_obligations
               WHERE obligation_type='withdrawal'
               ORDER BY created_at DESC,id DESC LIMIT 1"""
        ).fetchone()
        self.c.execute(
            "UPDATE syndication_delivery_obligations SET due_at=? WHERE id=?",
            (int(time.time())-1,obligation["id"]),
        )
        result=delivery_protocol.reconcile_sla(self.c)
        self.assertGreaterEqual(result["breachedObligations"],1)
        q=syndication_network.qualification_snapshot(self.c,"INST-DELIVERY-001")
        self.assertEqual(q["qualification"]["status"],"requalification_due")
        evaluation=result["evaluations"][0]
        self.assertTrue(evaluation["requalificationDue"])
        self.assertTrue(evaluation["suspensionReviewRecommended"])
        self.assertFalse(evaluation["automaticSuspension"])
        self.assertFalse(evaluation["automaticRevocation"])

    def test_three_missing_acknowledgements_trigger_requalification_only(self):
        self._subscribe()
        package,delivery=self._package_and_delivery()
        first_event=delivery["outboundEvent"]["id"]
        self._dispatch_success(first_event)

        for index in (2,3):
            event=delivery_protocol.create_event(
                self.c,
                "INST-DELIVERY-001",
                "qualification_status",
                "qualification",
                f"synthetic-{index}",
                {"state":"qualified","iteration":index},
                "governance@demo.ru",
                demo_only=True,
            )
            self._dispatch_success(event["id"])

        old=int(time.time())-delivery_protocol.ACK_EXPECTATION_SECONDS-5
        self.c.execute(
            """UPDATE syndication_delivery_event_state
               SET delivered_at=? WHERE status='delivered'""",
            (old,),
        )
        result=delivery_protocol.reconcile_sla(self.c)
        self.assertEqual(result["missingAcknowledgements"],3)
        q=syndication_network.qualification_snapshot(self.c,"INST-DELIVERY-001")
        self.assertEqual(q["qualification"]["status"],"requalification_due")
        evaluation=result["evaluations"][0]
        self.assertEqual(evaluation["evidence"]["missingAcknowledgements"],3)
        self.assertFalse(evaluation["automaticSuspension"])
        self.assertFalse(evaluation["automaticRevocation"])

    def test_delivery_attempt_and_ack_audit_tables_are_immutable(self):
        self._subscribe()
        _,delivery=self._package_and_delivery()
        event_id=delivery["outboundEvent"]["id"]
        dispatched,_=self._dispatch_success(event_id)
        self._ack(event_id)
        self.c.commit()

        with self.assertRaises(Exception):
            self.c.execute(
                "UPDATE syndication_delivery_attempts SET http_status=299 WHERE id=?",
                (dispatched["attemptId"],),
            )
        self.c.rollback()
        with self.assertRaises(Exception):
            self.c.execute(
                "DELETE FROM syndication_delivery_acknowledgements WHERE event_id=?",
                (event_id,),
            )
        self.c.rollback()


def hashlib_sha(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


if __name__=="__main__":
    unittest.main()
