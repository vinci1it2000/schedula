import React, {Suspense} from "react";
import {nanoid} from "nanoid";
const Accordion = React.lazy(() => import('@mui/material/Accordion'));
const AccordionSummary = React.lazy(() => import('@mui/material/AccordionSummary'));
const Typography = React.lazy(() => import('@mui/material/Typography'));
const AccordionDetails = React.lazy(() => import('@mui/material/AccordionDetails'));
const Stack = React.lazy(() => import('@mui/material/Stack'));
const ExpandMoreIcon = React.lazy(() => import('@mui/icons-material/ExpandMore'));


export default function _accordion(props) {
    let elements = (props.elements || {}), id = nanoid();
    return <Suspense>
        <Stack spacing={1} {...props}>
            {props.children.map((element, index) => (
                <Accordion key={index}
                           TransitionProps={{unmountOnExit: true}} {...(elements[index] || {}).props}>
                    <AccordionSummary
                        sx={{"backgroundColor": "lightgray"}}
                        expandIcon={
                            <ExpandMoreIcon/>
                        } aria-controls={id + index + "-content"}
                        id={id + index + "-header"} {...(elements[index] || {}).propsSummary}>
                        <Typography>{(elements[index] || {}).name || ((element.props || {}).schema || {}).title || (element.props || {}).name}</Typography>
                    </AccordionSummary>
                    <AccordionDetails
                        id={id + index + "-details"} {...(elements[index] || {}).propsDetails}>
                        {element}
                    </AccordionDetails>
                </Accordion>
            ))}
        </Stack>
    </Suspense>
}