import MarkdownWidget from './MarkdownWidget'
import ReCAPTCHAWidget from './ReCAPTCHA'
import ValueWidget from './ValueWidget'

export function generateWidgets() {
    return {
        MarkdownWidget,
        ReCAPTCHAWidget,
        ValueWidget
    }
}

export default generateWidgets();
