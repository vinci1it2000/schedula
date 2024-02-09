import {generateWidgets as coreGenerateWidgets} from "../../../core/widgets";
import {generateWidgets as antdGenerateWidgets} from "@rjsf/antd";
import ButtonWidget from "./ButtonWidget";
import CheckboxWidget from './CheckboxWidget'
import DateRangeWidget from './DateRangeWidget'
import FileWidget from "./FileWidget";
import MentionsWidget from "./MentionsWidget";
import RangeWidget from "./RangeWidget";
import RateWidget from "./RateWidget";
import SelectWidget from "./SelectWidget";
import SwitchWidget from "./SwitchWidget";
import TransferWidget from "./TransferWidget";

export function generateWidgets() {
    return {
        ...coreGenerateWidgets(), ...antdGenerateWidgets(),
        ButtonWidget,
        CheckboxWidget,
        DateRangeWidget,
        FileWidget,
        MentionsWidget,
        RangeWidget,
        RateWidget,
        SelectWidget,
        SwitchWidget,
        TransferWidget
    };
}

export default generateWidgets();
