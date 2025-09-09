import {Chatter} from "@mail/chatter/web_portal/chatter";
import {FailedMessage} from "@mail_tracking/components/failed_message/failed_message.esm";
import {patch} from "@web/core/utils/patch";

const {useState} = owl;

Chatter.components = {
    ...Chatter.components,
    FailedMessage,
};

/** @type {import("@mail/core/common/chatter").Chatter} */
const ChatterPatch = {
    setup() {
        super.setup(...arguments);
        this.state = useState({
            ...this.state,
            showFailedMessageList: true,
        });
    },
    toggleFailedMessageList() {
        this.state.showFailedMessageList = !this.state.showFailedMessageList;
    },
};

patch(Chatter.prototype, ChatterPatch);
