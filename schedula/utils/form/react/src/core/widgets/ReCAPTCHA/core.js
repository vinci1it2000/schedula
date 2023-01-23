import ReCAPTCHA from "react-google-recaptcha";

export default function ReCAPTCHAWidget({id, onChange, options, formContext}) {
    const {form, reCAPTCHA: sitekey} = formContext
    return <ReCAPTCHA
        id={id}
        sitekey={sitekey}
        {...options}
        onChange={onChange}
        hl={form.state.language.replace('_', '-')}/>
}