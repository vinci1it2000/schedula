import React, {Suspense} from "react";
const Box = React.lazy(() => import('@mui/material/Box'));
const TextField = React.lazy(() => import('@mui/material/TextField'));

const InputComponent = React.forwardRef(
    function InputComponent(props, ref) {
        return <Box sx={{width: "100%"}}>
            <input ref={ref} hidden/>
            <div {...props} />
        </Box>
    }
);
const BorderedSection = ({children, label, ...props}) => {
    return <Suspense>
        <TextField
            sx={{
                "& .MuiInputBase-root": {
                    minHeight: 56
                }
            }}
            variant="outlined"
            label={label}
            multiline
            InputLabelProps={{shrink: true}}
            InputProps={{
                inputComponent: InputComponent
            }}
            fullWidth
            inputProps={{children: children}}
            size={"small"}
            {...props}
        />
    </Suspense>
};
export default BorderedSection;