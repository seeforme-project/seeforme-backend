// In seeforme-backend/functions/index.js

const functions = require("firebase-functions");
const admin = require("firebase-admin");
admin.initializeApp();

const db = admin.firestore();
const messaging = admin.messaging();

exports.findVolunteerAndNotify = functions.https.onCall(
    async (data, context) => {
      const meetingId = data.meetingId;

      if (!meetingId) {
        throw new functions.https.HttpsError(
            "invalid-argument",
            "Missing meetingId.",
        );
      }

      const snapshot = await db
          .collection("volunteers")
          .where("isAvailable", "==", true)
          .limit(1)
          .get();

      if (snapshot.empty) {
        throw new functions.https.HttpsError(
            "not-found",
            "No volunteers are available.",
        );
      }

      const volunteerDoc = snapshot.docs[0];
      const volunteerId = volunteerDoc.id;
      const fcmToken = volunteerDoc.data().fcmToken;

      if (!fcmToken) {
        throw new functions.https.HttpsError(
            "internal",
            "Volunteer has no notification token.",
        );
      }

      // Reserve the volunteer
      await db
          .collection("volunteers")
          .doc(volunteerId)
          .update({isAvailable: false});

      const payload = {
        notification: {
          title: "Incoming Call for Assistance!",
          body: "A user needs your help. Tap to answer.",
        },
        data: {
          meetingId: meetingId,
          type: "INCOMING_CALL", // Custom type for our app to identify the call
        },
      };

      try {
        await messaging.sendToDevice(fcmToken, payload);
        console.log(`Notification sent to volunteer ${volunteerId}`);
        return {success: true};
      } catch (error) {
        console.error("Failed to send notification:", error);
        // Un-reserve the volunteer if sending failed
        await db
            .collection("volunteers")
            .doc(volunteerId)
            .update({isAvailable: true});
        throw new functions.https.HttpsError(
            "internal",
            "Failed to send notification.",
        );
      }
    },
);
