# Twitter/X Engagement Procedure

## Check Mentions (Do This First)
```bash
python twitter/client.py new-mentions
```
- Uses `since_id` to only fetch NEW mentions since last check
- Auto-filters already-replied tweets
- Updates `.twitter_state.json` with last_mention_id

## Reply to New Mentions
```python
client.post_tweet("reply text", reply_to="TWEET_ID", reply_author="USERNAME")
```
- Auto-tracks in `replied_to` list (won't show again in new-mentions)
- Auto-logs 5W interaction (WHO/WHAT/WHY/WHERE/WHEN)
- **Duplicate guard built-in**: `post_tweet()` checks `.twitter_state.json` BEFORE sending.
  If already replied, returns `{"duplicate_blocked": True}` and logs `[DEDUP]` to stderr.
  Use `force=True` (Python) or `--force` (CLI) to override if intentional.

## If No New Mentions
- Freely explore: `python twitter/client.py timeline`
- Search topics: `python twitter/client.py search "AI agents"`
- Like good tweets: `python twitter/client.py like TWEET_ID`
- Post original content

## NEVER Do
- Use `mentions` (returns ALL mentions including old ones)
- Reply to the same tweet twice (enforced by action-level dedup guard in post_tweet)
- Reply to Lex's (@cscdegen) mentions of me (he's tagging me for others)

## State File
- Location: `twitter/.twitter_state.json`
- Tracks: last_mention_id, replied_to[], liked_tweets[], interactions[]
- Each interaction has: who, what (tweet_id), why (reply/like), where (twitter), when

## View Contacts
```bash
python twitter/client.py contacts
```
Shows aggregated 5W interaction history per person.
