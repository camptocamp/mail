import {useService} from "@web/core/utils/hooks";

const {Component, useState} = owl;

export class FailedMessageReview extends Component {
    static props = ["message"];
    static template = "mail_tracking.FailedMessageReview";

    setup() {
        this.orm = useService("orm");
    }
    async setFailedMessageReviewed() {
        // TODO: Drop this method and rely exclusively on the core mail.resend.message
        // wizard and its "Ignore all" button.
        await this.orm.call("mail.message", "set_need_action_done", [
            [this.props.message.id],
        ]);
    }
    retryFailedMessage() {
        this.env.services.action.doAction("mail.mail_resend_message_action", {
            additionalContext: {
                mail_message_to_resend: this.props.message.id,
            },
        });
    }
}
